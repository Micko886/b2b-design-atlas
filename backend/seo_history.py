"""V72 - persistent, opt-in, published-only SEO audit history.

Snapshots contain public IDs and editorial issue codes, not drafts, user data,
source HTML, or any search-platform ranking claims.
"""
from __future__ import annotations
import json
import re
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, Request

from app import cms_quality, cms_routes, user_auth

UUID_RE=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
KINDS=("site","module","pattern","article")
MAX_DETAILS=16

def build_snapshot(catalog):
    """Pure report of *all* published content, independent of UI's 100-item cap."""
    records=[]
    issues=[]
    sections=[]
    for kind in KINDS:
        source=catalog.get(cms_quality._KIND_MAP[kind][0],{}) if isinstance(catalog,dict) else {}
        source=source if isinstance(source,dict) else {}
        duplicates=cms_quality.duplicate_map(kind,catalog)
        total=flagged=high=0
        for slug in sorted(key for key in source if isinstance(key,str)):
            if not isinstance(slug,str) or not cms_routes.SLUG.fullmatch(slug):
                continue
            item=source[slug]
            total+=1
            records.append(kind+":"+slug)
            report=cms_quality.audit_resource(kind,slug,item,catalog,duplicates.get(slug))
            if not report["issue_count"]:continue
            flagged+=1
            if report["priority"]=="high":high+=1
            for issue in report["issues"]:
                issues.append({"kind":kind,"slug":slug,
                               "code":str(issue["code"])[:80],
                               "priority":str(issue["priority"])[:12],
                               "title":str(report["title"])[:140],
                               "label":str(issue["label"])[:120]})
        sections.append({"kind":kind,"total":total,"flagged":flagged,
                         "high":high,"clear":total-flagged})
    summary={key:sum(section[key] for section in sections)
             for key in ("total","flagged","high","clear")}
    summary["issues"]=len(issues)
    summary["sections"]=sections
    return {"summary":summary,"records":records,"issues":issues}


def _key(item):
    return (item["kind"],item["slug"],item["code"])


def compare_snapshots(before,after):
    """Compare issue identities, treating removed public records separately."""
    old_public=set(before["records"])
    new_public=set(after["records"])
    old={_key(x):x for x in before["issues"]}
    new={_key(x):x for x in after["issues"]}
    still_public=old_public & new_public
    resolved=[old[k] for k in old.keys()-new.keys()
              if old[k]["kind"]+":"+old[k]["slug"] in still_public]
    unpublished=[old[k] for k in old.keys()-new.keys()
                 if old[k]["kind"]+":"+old[k]["slug"] not in new_public]
    introduced=[new[k] for k in new.keys()-old.keys()]
    persisting=[new[k] for k in new.keys()&old.keys()]
    def order(rows):
        return sorted(rows,key=lambda x:(x["kind"],x["slug"],x["code"]))
    return {
        "resolved_count":len(resolved),
        "introduced_count":len(introduced),
        "persisting_count":len(persisting),
        "unpublished_issue_count":len(unpublished),
        "unpublished_record_count":len(old_public-new_public),
        "new_record_count":len(new_public-old_public),
        "resolved":order(resolved)[:MAX_DETAILS],
        "introduced":order(introduced)[:MAX_DETAILS],
        "persisting":order(persisting)[:MAX_DETAILS],
        "unpublished":order(unpublished)[:MAX_DETAILS],
        "note":"按公开记录标识及问题代码对比。下线/归档与修复分开计数；重新发布的内容产生的新问题计入新增。"
    }


def _decode(row):
    return {"id":row["id"],"created_at":row["created_at"],
            "summary":json.loads(row["summary_json"]),
            **json.loads(row["snapshot_json"])}


def _meta(snapshot):
    return {"id":snapshot["id"],"created_at":snapshot["created_at"],
            "summary":snapshot["summary"]}


def _load(db,snapshot_id):
    if not UUID_RE.fullmatch(snapshot_id):
        user_auth.error(422,"巡检快照 ID 无效。")
    row=db.one("""SELECT id,created_at,summary_json,snapshot_json
                   FROM atlas_cms_seo_snapshots WHERE id=?""",(snapshot_id,))
    if not row:user_auth.error(404,"巡检快照不存在。")
    return _decode(row)


def save_snapshot(actor_id,catalog):
    """Only explicit authenticated POST persists a snapshot; never implicit GET."""
    record=build_snapshot(catalog)
    snapshot_id=str(uuid.uuid4())
    at=datetime.now(timezone.utc).isoformat(timespec="microseconds")
    cms_routes.ensure_cms()
    with user_auth.db() as db:
        db.execute("""INSERT INTO atlas_cms_seo_snapshots
           (id,created_at,created_by,summary_json,snapshot_json)
           VALUES(?,?,?,?,?)""",
           (snapshot_id,at,actor_id,
            json.dumps(record["summary"],ensure_ascii=False,separators=(",",":")),
            json.dumps({"records":record["records"],"issues":record["issues"]},
                       ensure_ascii=False,separators=(",",":"))))
    return {"id":snapshot_id,"created_at":at,"summary":record["summary"]}


def history(limit=12):
    cms_routes.ensure_cms()
    with user_auth.db() as db:
        rows=db.all("""SELECT id,created_at,summary_json,snapshot_json
                       FROM atlas_cms_seo_snapshots
                       ORDER BY created_at DESC,id DESC LIMIT ?""",(limit,))
    snapshots=[_decode(row) for row in rows]
    return {"snapshots":[_meta(x) for x in snapshots],
            "latest_comparison":(
                {"base":_meta(snapshots[1]),"current":_meta(snapshots[0]),
                 "changes":compare_snapshots(snapshots[1],snapshots[0])}
                if len(snapshots)>=2 else None),
            "note":"历史记录只在授权人员明确保存全站快照时生成；仅代表保存时公开内容的基础质量检查。"}


def compare_ids(base_id,current_id):
    if base_id==current_id:user_auth.error(422,"请选择两个不同的历史快照。")
    cms_routes.ensure_cms()
    with user_auth.db() as db:
        base=_load(db,base_id)
        current=_load(db,current_id)
    if base["created_at"]>current["created_at"]:
        user_auth.error(422,"基准快照不能晚于对比快照。")
    return {"base":_meta(base),"current":_meta(current),
            "changes":compare_snapshots(base,current)}


def register_history_routes(app:FastAPI):
    @app.get("/api/admin/seo/history",include_in_schema=False)
    def list_seo_snapshots(request:Request):
        cms_routes.require_admin(request,permission="view")
        return history()

    @app.get("/api/admin/seo/history/compare",include_in_schema=False)
    def compare_seo_snapshots(request:Request,base:str,current:str):
        cms_routes.require_admin(request,permission="view")
        return compare_ids(base,current)

    @app.post("/api/admin/seo/history",include_in_schema=False,status_code=201)
    def record_seo_snapshot(request:Request):
        actor=cms_routes.require_admin(request,mutate=True,permission="edit")
        # The public catalog contains CMS *published* snapshots, never drafts.
        catalog=cms_routes.seo_routes.catalog()
        return save_snapshot(actor["user_id"],catalog)
