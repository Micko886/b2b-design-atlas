"""Safe scheduled publishing for reviewed CMS snapshots.

The free Render web service may sleep, so due releases are finalized on the
next public catalog request or schedule API check. Never claim exact-time
execution without an always-on worker. Optimistic revision guards prevent
outdated schedules from publishing later edits.
"""
from __future__ import annotations
import re
import threading
import time
import uuid
from datetime import datetime,timezone,timedelta
from typing import Literal
from fastapi import FastAPI,Request
from pydantic import BaseModel,Field
from app import cms_routes,user_auth

CHECK_LOCK=threading.Lock()
LAST_CHECK=0.0
SLUG=cms_routes.SLUG
KIND=cms_routes.KIND

class ScheduleRequest(BaseModel):
    expected_revision: int=Field(ge=1)
    publish_at: str=Field(min_length=19,max_length=40)

def parse_publish_time(value,now=None):
    now=now or datetime.now(timezone.utc)
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except (TypeError,ValueError,AttributeError):
        user_auth.error(422,"请选择有效的发布时间。")
    if dt.tzinfo is None or dt.utcoffset() is None:
        user_auth.error(422,"发布时间必须包含时区，请提交 UTC 时间。")
    dt=dt.astimezone(timezone.utc)
    if dt<=now+timedelta(seconds=60):
        user_auth.error(422,"请将发布时间设为至少 1 分钟后。")
    if dt>now+timedelta(days=365):
        user_auth.error(422,"最多允许安排未来 365 天内的发布。")
    return dt.isoformat(timespec="seconds")

def save_event(db,kind,slug,action,actor_id,details):
    db.execute("""INSERT INTO atlas_cms_schedule_history
       (id,kind,slug,action,actor_id,details,created_at) VALUES(?,?,?,?,?,?,?)""",
       (str(uuid.uuid4()),kind,slug,action,actor_id,details,cms_routes.utc_now()))

def publish_due(now=None,force=False):
    """Publish only reviewed, exact-revision due items. Fail safely otherwise."""
    global LAST_CHECK
    moment=time.monotonic()
    if not force and moment-LAST_CHECK<30:return 0
    if not CHECK_LOCK.acquire(blocking=False):return 0
    try:
        if not force and moment-LAST_CHECK<30:return 0
        LAST_CHECK=moment
        now=now or datetime.now(timezone.utc)
        now_iso=now.isoformat(timespec="seconds")
        cms_routes.ensure_cms()
        published=0
        with user_auth.db() as db:
            due=db.all("""SELECT * FROM atlas_cms_schedules
                 WHERE status='pending' AND publish_at<=?
                 ORDER BY publish_at ASC LIMIT 25""",(now_iso,))
            for scheduled in due:
                kind,slug=scheduled["kind"],scheduled["slug"]
                row=db.one("SELECT * FROM atlas_cms_entries WHERE kind=? AND slug=?",(kind,slug))
                if not row or row["status"]!="review" or row["revision"]!=scheduled["revision"]:
                    db.execute("""UPDATE atlas_cms_schedules SET status='stale',error=?,
                       updated_at=? WHERE kind=? AND slug=? AND status='pending'""",
                       ("草稿版本或审核状态已改变，已阻止自动发布。",now_iso,kind,slug))
                    save_event(db,kind,slug,"stale",scheduled["created_by"],"审核状态或版本变化")
                    continue
                try:
                    cms_routes.verify_links(kind,cms_routes.parse_json(row["draft_json"]))
                except Exception:
                    db.execute("""UPDATE atlas_cms_schedules SET status='failed',error=?,
                       updated_at=? WHERE kind=? AND slug=? AND status='pending'""",
                       ("发布校验未通过，请修正内容并重新排期。",now_iso,kind,slug))
                    save_event(db,kind,slug,"failed",scheduled["created_by"],"发布校验失败")
                    continue
                revision=row["revision"]+1
                changed=db.execute("""UPDATE atlas_cms_entries SET
                    status='published',published_json=draft_json,published_at=?,
                    published_by=?,revision=?,updated_by=?,updated_at=?
                    WHERE kind=? AND slug=? AND revision=? AND status='review'""",
                    (now_iso,scheduled["created_by"],revision,scheduled["created_by"],
                     now_iso,kind,slug,row["revision"]))
                if changed.rowcount!=1:
                    db.execute("""UPDATE atlas_cms_schedules SET status='stale',
                      error='版本冲突，自动发布已取消。',updated_at=?
                      WHERE kind=? AND slug=? AND status='pending'""",(now_iso,kind,slug))
                    continue
                db.execute("""UPDATE atlas_cms_schedules SET status='published',
                    error='',updated_at=? WHERE kind=? AND slug=? AND status='pending'""",
                    (now_iso,kind,slug))
                cms_routes.log_change(db,{"kind":kind,"slug":slug,"revision":revision,
                         "draft_json":row["draft_json"]},"scheduled_publish",scheduled["created_by"])
                save_event(db,kind,slug,"published",scheduled["created_by"],now_iso)
                published+=1
        if published:cms_routes.invalidate()
        return published
    finally:
        CHECK_LOCK.release()

def register_schedule_routes(app:FastAPI):
    @app.get("/api/admin/schedules",include_in_schema=False)
    def list_schedules(request:Request,status:str=""):
        cms_routes.require_admin(request)
        publish_due(force=True)
        cms_routes.ensure_cms()
        with user_auth.db() as db:
            rows=db.all("""SELECT s.kind,s.slug,s.revision,s.publish_at,s.status,
                      s.error,s.created_at,s.updated_at,e.status AS content_status,
                      e.revision AS current_revision
                      FROM atlas_cms_schedules s LEFT JOIN atlas_cms_entries e
                      ON e.kind=s.kind AND e.slug=s.slug
                      ORDER BY CASE WHEN s.status='pending' THEN 0 ELSE 1 END,
                      s.publish_at DESC LIMIT 160""")
            history=db.all("""SELECT kind,slug,action,actor_id,details,created_at
                      FROM atlas_cms_schedule_history ORDER BY created_at DESC LIMIT 40""")
        if status in ("pending","published","failed","stale","cancelled"):
            rows=[x for x in rows if x["status"]==status]
        return {"items":rows,"history":history,
                "execution_note":"Render 免费 Web 服务休眠时无法按分钟持续执行；到期发布在下一次公开目录请求或排期列表检查时触发。"}

    @app.post("/api/admin/content/{kind}/{slug}/schedule",include_in_schema=False)
    def schedule(kind:KIND,slug:str,data:ScheduleRequest,request:Request):
        session=cms_routes.require_admin(request,mutate=True,permission="review")
        if not SLUG.fullmatch(slug):user_auth.error(422,"内容标识无效。")
        publish_at=parse_publish_time(data.publish_at)
        cms_routes.ensure_cms()
        with user_auth.db() as db:
            row=db.one("SELECT * FROM atlas_cms_entries WHERE kind=? AND slug=?",(kind,slug))
            if not row:user_auth.error(404,"内容尚无草稿。")
            if row["status"]!="review":user_auth.error(409,"只有已提交审核的内容可以排期发布。")
            if row["revision"]!=data.expected_revision:
                user_auth.error(409,"内容版本已改变，请刷新后重新安排发布时间。")
            cms_routes.verify_links(kind,cms_routes.parse_json(row["draft_json"]))
            moment=cms_routes.utc_now();uid=session["user_id"]
            db.execute("""INSERT INTO atlas_cms_schedules
               (kind,slug,revision,publish_at,status,created_by,created_at,updated_at,error)
               VALUES(?,?,?,?,'pending',?,?,?,'')
               ON CONFLICT(kind,slug) DO UPDATE SET revision=excluded.revision,
                 publish_at=excluded.publish_at,status='pending',created_by=excluded.created_by,
                 updated_at=excluded.updated_at,error=''""",
               (kind,slug,row["revision"],publish_at,uid,moment,moment))
            save_event(db,kind,slug,"schedule",uid,publish_at)
        return {"ok":True,"kind":kind,"slug":slug,"publish_at":publish_at,"status":"pending"}

    @app.delete("/api/admin/content/{kind}/{slug}/schedule",include_in_schema=False)
    def cancel(kind:KIND,slug:str,request:Request):
        session=cms_routes.require_admin(request,mutate=True,permission="review")
        cms_routes.ensure_cms()
        with user_auth.db() as db:
            old=db.one("SELECT status FROM atlas_cms_schedules WHERE kind=? AND slug=?",(kind,slug))
            if not old or old["status"]!="pending":
                user_auth.error(409,"当前没有可取消的待发布排期。")
            db.execute("""UPDATE atlas_cms_schedules SET status='cancelled',
                updated_at=?,error='' WHERE kind=? AND slug=? AND status='pending'""",
                (cms_routes.utc_now(),kind,slug))
            save_event(db,kind,slug,"cancel",session["user_id"],"")
        return {"ok":True,"kind":kind,"slug":slug,"status":"cancelled"}
