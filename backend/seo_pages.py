"""V57 · Reviewed SEO metadata for homepage and public collection pages.

Drafts and review submissions are private. Only approved snapshots reach
server-rendered HTML and the public SPA's metadata. No migrations of legacy
content or automatic publication.
"""
from __future__ import annotations

import json
import re
import threading
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from app import user_auth, cms_access

PAGE_KEYS=("home","websites","sections","patterns","insights")
PAGE_LOCK=threading.Lock()
PAGE_READY=False
PAGE_SCHEMA="""CREATE TABLE IF NOT EXISTS atlas_seo_pages(
    page TEXT PRIMARY KEY,
    draft_json TEXT NOT NULL,
    published_json TEXT,
    status TEXT NOT NULL CHECK(status IN ('draft','review','published')),
    revision INTEGER NOT NULL DEFAULT 1,
    updated_by TEXT NOT NULL,
    published_by TEXT,
    updated_at TEXT NOT NULL,
    published_at TEXT
)"""
MEDIA=re.compile(r"/api/media/[0-9a-f-]{36}$")


def ensure_pages():
    global PAGE_READY
    if PAGE_READY:return
    user_auth.ensure_ready()
    with PAGE_LOCK:
        if PAGE_READY:return
        with user_auth.db() as db:db.execute(PAGE_SCHEMA)
        PAGE_READY=True


def validate_page(page):
    if page not in PAGE_KEYS:user_auth.error(404,"该栏目不存在。")
    return page


def validate_payload(payload):
    from app import seo_routes
    if not isinstance(payload,dict):user_auth.error(422,"SEO 设置格式不正确。")
    if set(payload)-{"seo_title","seo_description","seo_image"}:
        user_auth.error(422,"SEO 设置包含不支持的字段。")
    clean={}
    for name,length in (("seo_title",100),("seo_description",300)):
        v=payload.get(name,"")
        if not isinstance(v,str) or len(v)>length:
            user_auth.error(422,name+" 格式或长度不正确。")
        clean[name]=v.strip()
    image=payload.get("seo_image","")
    if not isinstance(image,str) or (image and not seo_routes.public_image(image)):
        user_auth.error(422,"分享封面必须为站内有效图片路径。")
    clean["seo_image"]=image
    return clean


def published_pages():
    """Only explicitly approved snapshots. Fallback to defaults if DB is down."""
    try:
        ensure_pages()
        with user_auth.db() as db:
            rows=db.all("SELECT page,published_json FROM atlas_seo_pages WHERE published_json IS NOT NULL")
        result={}
        for row in rows:
            try:
                value=json.loads(row["published_json"])
                if isinstance(value,dict) and row["page"] in PAGE_KEYS:
                    result[row["page"]]=validate_payload(value)
            except (TypeError,ValueError):
                continue
        return result
    except Exception:
        # Never expose pending copy when the database is temporarily unavailable.
        return {}


class PageDraft(BaseModel):
    expected_revision:int=Field(ge=0)
    payload:dict


class PageChange(BaseModel):
    expected_revision:int=Field(ge=1)


def register_page_seo_routes(app:FastAPI):
    from app import cms_routes

    @app.get("/api/admin/seo/pages",include_in_schema=False)
    def page_list(request:Request):
        cms_routes.require_admin(request,permission="view")
        ensure_pages()
        with user_auth.db() as db:
            rows=db.all("SELECT page,draft_json,published_json,status,revision,updated_at,published_at FROM atlas_seo_pages")
        by_key={r["page"]:r for r in rows}
        defaults=cms_routes.seo_routes.PUBLIC
        items=[]
        for key in PAGE_KEYS:
            row=by_key.get(key)
            initial=defaults["" if key=="home" else key]
            items.append({
                "page":key,"default_title":initial[0],"default_description":initial[1],
                "payload":json.loads(row["draft_json"]) if row else {},
                "published":json.loads(row["published_json"]) if row and row["published_json"] else {},
                "status":row["status"] if row else "default",
                "revision":row["revision"] if row else 0,
                "updated_at":row["updated_at"] if row else "",
                "published_at":row["published_at"] if row else ""})
        return {"pages":items}

    @app.put("/api/admin/seo/pages/{page}",include_in_schema=False)
    def page_save(page:str,data:PageDraft,request:Request):
        cms_routes.require_admin(request,mutate=True,permission="edit")
        validate_page(page)
        payload=validate_payload(data.payload)
        ensure_pages()
        now=cms_routes.utc_now()
        uid=user_auth.required(request)["user_id"]
        with user_auth.db() as db:
            row=db.one("SELECT revision FROM atlas_seo_pages WHERE page=?",(page,))
            if not row:
                if data.expected_revision!=0:user_auth.error(409,"设置已变更，请重新加载。")
                db.execute("""INSERT INTO atlas_seo_pages
                    (page,draft_json,published_json,status,revision,updated_by,updated_at)
                    VALUES(?,?,NULL,'draft',1,?,?)""",
                    (page,json.dumps(payload,ensure_ascii=False),uid,now))
                revision=1
            else:
                if row["revision"]!=data.expected_revision:user_auth.error(409,"设置已被其他管理员更新，请刷新。")
                revision=row["revision"]+1
                updated=db.execute("""UPDATE atlas_seo_pages SET draft_json=?,status='draft',
                    revision=?,updated_by=?,updated_at=?
                    WHERE page=? AND revision=?""",
                    (json.dumps(payload,ensure_ascii=False),revision,uid,now,page,data.expected_revision))
                if updated.rowcount!=1:user_auth.error(409,"设置版本冲突，请重试。")
        return {"ok":True,"status":"draft","revision":revision}

    def change(page,expected,action,request):
        permission="review" if action in ("publish","reject") else "edit"
        session=cms_routes.require_admin(request,mutate=True,permission=permission)
        validate_page(page)
        ensure_pages()
        now=cms_routes.utc_now()
        with user_auth.db() as db:
            row=db.one("SELECT * FROM atlas_seo_pages WHERE page=?",(page,))
            if not row:user_auth.error(404,"请先保存设置草稿。")
            if row["revision"]!=expected:user_auth.error(409,"设置已更新，请刷新后重试。")
            if action=="submit":
                if row["status"]!="draft":user_auth.error(409,"仅草稿可以提交审核。")
                status="review";published=row["published_json"]
            elif action=="reject":
                if row["status"]!="review":user_auth.error(409,"只能退回待审核设置。")
                status="draft";published=row["published_json"]
            else:
                if row["status"]!="review":user_auth.error(409,"必须先提交审核才能发布。")
                draft=json.loads(row["draft_json"])
                validate_payload(draft)
                image=draft.get("seo_image","")
                if MEDIA.fullmatch(image):
                    if not db.one("SELECT id FROM atlas_cms_media WHERE id=?",(image.rsplit("/",1)[-1],)):
                        user_auth.error(422,"SEO 分享图片已不存在，请重新选择。")
                status="published";published=row["draft_json"]
            revision=expected+1
            updated=db.execute("""UPDATE atlas_seo_pages SET status=?,published_json=?,
                revision=?,updated_by=?,updated_at=?,
                published_by=?,published_at=?
                WHERE page=? AND revision=?""",
                (status,published,revision,session["user_id"],now,
                 session["user_id"] if action=="publish" else row["published_by"],
                 now if action=="publish" else row["published_at"],page,expected))
            if updated.rowcount!=1:user_auth.error(409,"设置已变化，请重新打开。")
        return {"ok":True,"page":page,"status":status,"revision":revision}

    @app.post("/api/admin/seo/pages/{page}/submit",include_in_schema=False)
    def page_submit(page:str,data:PageChange,request:Request):
        return change(page,data.expected_revision,"submit",request)

    @app.post("/api/admin/seo/pages/{page}/publish",include_in_schema=False)
    def page_publish(page:str,data:PageChange,request:Request):
        return change(page,data.expected_revision,"publish",request)

    @app.post("/api/admin/seo/pages/{page}/reject",include_in_schema=False)
    def page_reject(page:str,data:PageChange,request:Request):
        return change(page,data.expected_revision,"reject",request)
