"""V47 · Secure additive content management overlay for B2B Atlas.

Existing 290 public resources stay in their immutable, deployable source files.
Only edited/new content is stored in PostgreSQL as drafts, reviewed versions
and published snapshots. A reviewed version is made public only on publish.
Public browsing never has access to draft or audit data.

Admin identities are explicit UUIDs from ATLAS_ADMIN_USER_IDS and every
mutation requires a valid session, same-site origin, and CSRF token.
"""
from __future__ import annotations

import json
import base64
import hashlib
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, Response as BinaryResponse
from pydantic import BaseModel, Field

from app import user_auth, admin_routes, seo_routes

KIND = Literal["site", "module", "pattern", "article"]
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,110}$")
KIND_CATALOG = {"site":"sites", "module":"modules", "pattern":"patterns", "article":"articles"}
KIND_ROUTE = {"site":"/websites/", "module":"/sections/", "pattern":"/patterns/", "article":"/insights/"}
CMS_LOCK = threading.Lock()
CMS_READY = False
CACHE_LOCK = threading.Lock()
CACHE = {"until":0.0, "items":{}}
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS atlas_cms_entries (
        kind TEXT NOT NULL CHECK(kind IN ('site','module','pattern','article')),
        slug TEXT NOT NULL,
        draft_json TEXT NOT NULL,
        published_json TEXT,
        status TEXT NOT NULL CHECK(status IN ('draft','review','published','archived')),
        revision INTEGER NOT NULL DEFAULT 1,
        created_by TEXT NOT NULL REFERENCES atlas_users(id),
        updated_by TEXT NOT NULL REFERENCES atlas_users(id),
        published_by TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        published_at TEXT,
        PRIMARY KEY(kind,slug)
    )""",
    """CREATE INDEX IF NOT EXISTS atlas_cms_entries_status ON atlas_cms_entries(kind,status)""",
    """CREATE TABLE IF NOT EXISTS atlas_cms_history (
        id TEXT PRIMARY KEY,kind TEXT NOT NULL,slug TEXT NOT NULL,
        revision INTEGER NOT NULL,action TEXT NOT NULL,
        actor_id TEXT NOT NULL,created_at TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        UNIQUE(kind,slug,revision)
    )""",
    """CREATE INDEX IF NOT EXISTS atlas_cms_history_item ON atlas_cms_history(kind,slug,revision)""",
    """CREATE TABLE IF NOT EXISTS atlas_cms_media (
        id TEXT PRIMARY KEY,
        file_name TEXT NOT NULL,
        mime_type TEXT NOT NULL,
        content_b64 TEXT NOT NULL,
        byte_size INTEGER NOT NULL,
        sha256 TEXT NOT NULL,
        uploaded_by TEXT NOT NULL REFERENCES atlas_users(id),
        created_at TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS atlas_cms_media_created ON atlas_cms_media(created_at)"""
]

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def require_admin(request: Request, mutate=False):
    session = user_auth.required(request)
    if not admin_routes.admin_allowed(session):
        user_auth.error(403,"此账号没有内容管理权限。")
    if mutate:
        user_auth.origin(request)
        user_auth.check_csrf(request, session)
    return session

def ensure_cms():
    global CMS_READY
    user_auth.ensure_ready()
    if CMS_READY:return
    with CMS_LOCK:
        if CMS_READY:return
        with user_auth.db() as db:
            for sql in SCHEMA:
                db.execute(sql)
        CMS_READY = True

def base_maps():
    return seo_routes.base_catalog()

def parse_json(s):
    return json.loads(s) if s else None

def published_overrides(rows, archived_keys):
    """Pure public-visibility rule: published snapshot wins, then archive tombstone.

    Drafts following an archive must never resurrect the original file-backed
    resource. A later successful publish replaces the tombstone with its new
    published snapshot.
    """
    overlays={}
    for row in rows:
        key=(row["kind"],row["slug"])
        if row["status"]=="archived":
            overlays[key]=None
        elif row["published_json"]:
            overlays[key]=parse_json(row["published_json"])
        elif key in archived_keys:
            overlays[key]=None
    return overlays

def active_overrides():
    """Short shared cache keeps public pages quick while allowing editing."""
    with CACHE_LOCK:
        if time.monotonic() < CACHE["until"]:
            return dict(CACHE["items"])
    try:
        ensure_cms()
        with user_auth.db() as db:
            rows=db.all("SELECT kind,slug,status,published_json FROM atlas_cms_entries")
            # An archived item remains unpublished while a new draft is edited.
            # Without the tombstone from history, original file-backed records
            # would silently reappear after a save/restore of archived content.
            archived=db.all("SELECT DISTINCT kind,slug FROM atlas_cms_history WHERE action='archive'")
        archived_keys={(r["kind"],r["slug"]) for r in archived}
        overlays=published_overrides(rows, archived_keys)
    except Exception:
        # The legacy immutable catalog remains available even if the new DB
        # is down. Only the administrative API must fail closed.
        return {}
    with CACHE_LOCK:
        CACHE["items"]=overlays
        CACHE["until"]=time.monotonic()+15
    return dict(overlays)

def invalidate():
    with CACHE_LOCK:
        CACHE["until"]=0.0
        CACHE["items"]={}

def merge_catalog(base):
    """Does not mutate seo_routes' cached immutable file catalog."""
    merged={k:dict(v) for k,v in base.items()}
    for (kind,slug),payload in active_overrides().items():
        coll=KIND_CATALOG[kind]
        if payload is None:merged[coll].pop(slug,None)
        else:merged[coll][slug]=payload
    return merged

def public_payload(kind: KIND):
    original=base_maps()
    merged=merge_catalog(original)
    if kind=="site":
        out=seo_routes.read_json(seo_routes.BASE/"app"/"source_index.json",{})
        out["sites"]=list(merged["sites"].values())
    elif kind=="module":
        out={"modules":list(merged["modules"].values()),
             "total":len(merged["modules"]),
             "source_policy":"Curated real page screenshots / published Atlas CMS"}
    elif kind=="pattern":
        out=list(merged["patterns"].values())
    else:
        out=seo_routes.read_json(seo_routes.STATIC/"assets"/"articles.json",{})
        out["articles"]=list(merged["articles"].values())
    return out

def cleaned(kind,slug,payload):
    if not SLUG.fullmatch(slug):user_auth.error(400,"URL 标识只能使用小写英文、数字与短横线。")
    if not isinstance(payload,dict):user_auth.error(422,"内容必须是 JSON 对象。")
    size=len(json.dumps(payload,ensure_ascii=False,separators=(",",":")))
    if size>(160000 if kind=="article" else 36000):
        user_auth.error(413,"内容超过此类型的大小限制。")
    result=dict(payload)
    if result.get("id",slug)!=slug:user_auth.error(422,"URL 标识 id 不允许修改。")
    result["id"]=slug
    required={"site":("name","url","sector","summary"),
              "module":("title","site_id","category","lesson"),
              "pattern":("title","family","question","principle"),
              "article":("title","subtitle","category","author","sections")}[kind]
    for field in required:
        val=result.get(field)
        if not val or (field=="sections" and not isinstance(val,list)):
            user_auth.error(422,"请填写或检查必填字段："+field)
        if field!="sections" and (not isinstance(val,str) or len(val)>1800):
            user_auth.error(422,field+" 格式不正确。")
    if kind=="site":
        u=urlparse(result["url"])
        if u.scheme not in ("http","https") or not u.netloc:
            user_auth.error(422,"网站 URL 必须是完整的 http(s) 地址。")
    if kind=="article" and result.get("cover_image"):
        if not isinstance(result["cover_image"],str) or not re.fullmatch(r"/api/media/[0-9a-f-]{36}",result["cover_image"]):
            user_auth.error(422,"文章封面只能选择已上传的媒体图片。")
    if kind=="article":
        for key,limit in (("tags",20),("takeaways",30)):
            value=result.get(key,[])
            if not isinstance(value,list) or len(value)>limit or any(
                not isinstance(s,str) or not s.strip() or len(s)>180 for s in value
            ):
                user_auth.error(422,key+" 必须是有效文本列表。")
        if result.get("reading_minutes") is not None:
            minutes=result["reading_minutes"]
            if not isinstance(minutes,int) or isinstance(minutes,bool) or not 1<=minutes<=240:
                user_auth.error(422,"阅读时间必须为 1 至 240 分钟。")
    if kind=="article":
        if len(result["sections"])>40:user_auth.error(422,"文章章节最多 40 个。")
        for s in result["sections"]:
            if not isinstance(s,dict) or not isinstance(s.get("title"),str):
                user_auth.error(422,"文章章节缺少标题。")
            if s.get("image") and (not isinstance(s["image"],str) or
                                  not re.fullmatch(r"/api/media/[0-9a-f-]{36}",s["image"])):
                user_auth.error(422,"章节图片只能从媒体资源库选择。")
            if s.get("image_caption") and (not isinstance(s["image_caption"],str) or len(s["image_caption"])>240):
                user_auth.error(422,"图片说明不可超过 240 字。")
    for field in ("screenshot_url","source_capture"):
        if field in result:
            value=result[field]
            if not isinstance(value,str) or (value and not re.fullmatch(r"/screenshots/[a-zA-Z0-9_./-]{1,200}",value)):
                user_auth.error(422,"截图只能引用本网站的 /screenshots 路径。")
            if ".." in value:user_auth.error(422,"截图路径不合法。")
    if kind=="pattern" and "modules" in result:
        if not isinstance(result["modules"],list) or len(result["modules"])>30 or any(not isinstance(x,str) or not SLUG.fullmatch(x) for x in result["modules"]):
            user_auth.error(422,"关联模块 ID 格式无效。")
    return result

def verify_links(kind,payload):
    current=seo_routes.catalog()
    if kind=="module" and payload["site_id"] not in current["sites"]:
        user_auth.error(422,"关联的网站不存在或尚未发布。")
    if kind=="article" and payload.get("cover_site") and payload["cover_site"] not in current["sites"]:
        user_auth.error(422,"封面关联网站尚未发布。")
    if kind=="article":
        referenced=[payload.get("cover_image","")]
        referenced += [s.get("image","") for s in payload.get("sections",[]) if isinstance(s,dict)]
        referenced=[v.rsplit("/",1)[-1] for v in referenced if v]
        if referenced:
            ensure_cms()
            with user_auth.db() as db:
                for media_id in set(referenced):
                    if not db.one("SELECT id FROM atlas_cms_media WHERE id=?",(media_id,)):
                        user_auth.error(422,"文章引用了已删除的图片，请从媒体库重新选择。")
    if kind=="article":
        for chapter in payload.get("sections",[]):
            paragraphs=chapter.get("paragraphs",[])
            if not isinstance(paragraphs,list) or not any(isinstance(v,str) and v.strip() for v in paragraphs):
                user_auth.error(422,"发布文章前，请为每个章节写入至少一段正文。")
    if kind=="pattern" and any(x not in current["modules"] for x in payload.get("modules",[])):
        user_auth.error(422,"设计模式关联了尚未发布的模块。")

class Create(BaseModel):
    kind: KIND
    slug: str = Field(min_length=1,max_length=111)
    payload: dict[str,Any]

class Draft(BaseModel):
    payload: dict[str,Any]
    expected_revision: int = Field(ge=0)

class Change(BaseModel):
    expected_revision: int = Field(ge=0)

class Restore(BaseModel):
    expected_revision: int = Field(ge=0)
    revision: int = Field(ge=1)

class MediaUpload(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    mime: Literal["image/jpeg","image/png","image/webp"]
    content: str = Field(min_length=16,max_length=2800000)

class BulkItem(BaseModel):
    slug: str = Field(min_length=1,max_length=111)
    expected_revision: int = Field(ge=1)

class BulkChange(BaseModel):
    kind: KIND
    action: Literal["submit","publish","archive"]
    items: list[BulkItem] = Field(min_length=1,max_length=20)


def log_change(db,row,action,uid):
    db.execute("""INSERT INTO atlas_cms_history(id,kind,slug,revision,action,actor_id,created_at,snapshot_json)
               VALUES(?,?,?,?,?,?,?,?)""",
               (str(uuid.uuid4()),row["kind"],row["slug"],row["revision"],action,uid,utc_now(),row["draft_json"]))

def base_item(kind,slug):
    return base_maps()[KIND_CATALOG[kind]].get(slug)

def cms_item(kind,slug,session):
    ensure_cms()
    with user_auth.db() as db:
        row=db.one("SELECT * FROM atlas_cms_entries WHERE kind=? AND slug=?",(kind,slug))
        history=db.all("""SELECT revision,action,actor_id,created_at FROM atlas_cms_history
                       WHERE kind=? AND slug=? ORDER BY revision DESC LIMIT 35""",(kind,slug))
    base=base_item(kind,slug)
    if not row and not base:user_auth.error(404,"内容不存在。")
    return {
        "kind":kind,"slug":slug,"source":"cms" if row else "repository",
        "status":row["status"] if row else "source",
        "revision":row["revision"] if row else 0,
        "payload":parse_json(row["draft_json"]) if row else base,
        "published":parse_json(row["published_json"]) if row and row["published_json"] else base if not row else None,
        "published_at":row["published_at"] if row else None,
        "history":history
    }

def register_cms_routes(app: FastAPI):
    @app.middleware("http")
    async def published_catalog_overlay(request:Request,call_next):
        path=request.url.path
        routes={
            "/api/source-library":"site",
            "/api/module-library":"module",
            "/assets/patterns.json":"pattern",
            "/assets/articles.json":"article"
        }
        if request.method=="GET" and path in routes:
            # Keep readonly public catalog accessible if no DB is configured.
            return JSONResponse(public_payload(routes[path]),headers={
                "Cache-Control":"no-cache","X-Atlas-Catalog":"published",
                "X-Content-Type-Options":"nosniff",
                "Referrer-Policy":"strict-origin-when-cross-origin",
                "X-Frame-Options":"DENY"
            })
        return await call_next(request)

    @app.get("/api/admin/content/taxonomy",include_in_schema=False)
    def taxonomy(request:Request):
        require_admin(request)
        current=seo_routes.catalog()
        result={}
        for kind,collection in KIND_CATALOG.items():
            attr="family" if kind=="pattern" else "sector" if kind=="site" else "category"
            values={str(v.get(attr,"")).strip() for v in current[collection].values() if isinstance(v,dict)}
            # Article categories are stable IDs in the public dataset; include
            # them even when they have no current articles.
            if kind=="article":
                configured=seo_routes.read_json(seo_routes.STATIC/"assets"/"articles.json",{})
                values.update(x["id"] for x in configured.get("categories",[]) if isinstance(x,dict) and x.get("id"))
            result[kind]=sorted(x for x in values if x)[:120]
        tag_counts={}
        for article in current["articles"].values():
            if not isinstance(article,dict):continue
            for tag in article.get("tags",[]):
                if not isinstance(tag,str) or not tag.strip() or len(tag)>32:continue
                tag_counts[tag.strip()]=tag_counts.get(tag.strip(),0)+1
        common_tags=sorted(tag_counts,key=lambda x:(-tag_counts[x],x))[:30]
        return {"categories":result,"article_tags":common_tags}

    @app.get("/api/admin/media",include_in_schema=False)
    def media_list(request:Request):
        require_admin(request);ensure_cms()
        with user_auth.db() as db:
            rows=db.all("SELECT id,file_name,mime_type,byte_size,sha256,created_at FROM atlas_cms_media ORDER BY created_at DESC LIMIT 150")
        return {"items":[{**r,"url":"/api/media/"+r["id"]} for r in rows]}

    @app.post("/api/admin/media",include_in_schema=False,status_code=201)
    def media_upload(data:MediaUpload,request:Request):
        session=require_admin(request,mutate=True);ensure_cms()
        try:
            contents=base64.b64decode(data.content,validate=True)
        except Exception:
            user_auth.error(422,"图片 Base64 数据不合法。")
        if len(contents)>1500000 or not contents:
            user_auth.error(413,"单张图片最大 1.5MB。")
        detected = (
            "image/png" if contents.startswith(b"\x89PNG\r\n\x1a\n") else
            "image/jpeg" if contents.startswith(b"\xff\xd8\xff") and contents.endswith(b"\xff\xd9") else
            "image/webp" if contents[:4]==b"RIFF" and contents[8:12]==b"WEBP" else None
        )
        if detected!=data.mime:
            user_auth.error(422,"图片格式与文件内容不一致。")
        file_name=re.sub(r"[^a-zA-Z0-9_.-]","_",data.name.split("/")[-1].split(chr(92))[-1])[:160]
        mid=str(uuid.uuid4())
        with user_auth.db() as db:
            db.execute("INSERT INTO atlas_cms_media(id,file_name,mime_type,content_b64,byte_size,sha256,uploaded_by,created_at) VALUES(?,?,?,?,?,?,?,?)",
                       (mid,file_name or "image",detected,data.content,len(contents),hashlib.sha256(contents).hexdigest(),session["user_id"],utc_now()))
        return {"id":mid,"url":"/api/media/"+mid,"name":file_name,"mime":detected,"size":len(contents)}

    @app.delete("/api/admin/media/{media_id}",include_in_schema=False)
    def delete_media(media_id:str,request:Request):
        require_admin(request,mutate=True);ensure_cms()
        try: uuid.UUID(media_id)
        except ValueError: user_auth.error(404,"图片不存在。")
        target="/api/media/"+media_id
        with user_auth.db() as db:
            if not db.one("SELECT id FROM atlas_cms_media WHERE id=?",(media_id,)):
                user_auth.error(404,"图片不存在。")
            # Check all CMS drafts and published snapshots. Archive/history
            # retains immutable audit snapshots, but active references forbid deletion.
            refs=db.all("SELECT kind,slug,draft_json,published_json FROM atlas_cms_entries")
            for row in refs:
                for field in ("draft_json","published_json"):
                    if target in (row[field] or ""):
                        user_auth.error(409,"该图片仍被内容引用，请先替换并保存对应文章。")
            db.execute("DELETE FROM atlas_cms_media WHERE id=?",(media_id,))
        return {"ok":True}

    @app.get("/api/media/{media_id}",include_in_schema=False)
    def serve_media(media_id:str):
        try:uuid.UUID(media_id)
        except ValueError:user_auth.error(404,"图片不存在。")
        ensure_cms()
        with user_auth.db() as db:
            row=db.one("SELECT mime_type,content_b64 FROM atlas_cms_media WHERE id=?",(media_id,))
        if not row:user_auth.error(404,"图片不存在。")
        return BinaryResponse(content=base64.b64decode(row["content_b64"]),media_type=row["mime_type"],
            headers={"Cache-Control":"public,max-age=86400","X-Content-Type-Options":"nosniff","Content-Security-Policy":"default-src 'none'; sandbox"})

    @app.post("/api/admin/content/bulk",include_in_schema=False)
    def bulk_change(data:BulkChange,request:Request):
        session=require_admin(request,mutate=True);ensure_cms()
        slugs=[x.slug for x in data.items]
        if len(set(slugs))!=len(slugs) or any(not SLUG.fullmatch(s) for s in slugs):
            user_auth.error(422,"请检查批量选择中是否有重复或非法标识。")
        now=utc_now();uid=session["user_id"]
        with user_auth.db() as db:
            # All-or-nothing transaction. Check ALL revisions and transitions
            # before mutating any record.
            checked=[]
            for item in data.items:
                row=db.one("SELECT * FROM atlas_cms_entries WHERE kind=? AND slug=?",(data.kind,item.slug))
                if not row or row["revision"]!=item.expected_revision:
                    user_auth.error(409,"版本已变化，请刷新选择后重试："+item.slug)
                if data.action=="submit" and row["status"]!="draft":
                    user_auth.error(409,"仅草稿可提交审核："+item.slug)
                if data.action=="publish" and row["status"]!="review":
                    user_auth.error(409,"仅待审核内容可发布："+item.slug)
                if data.action=="archive" and row["status"]!="published":
                    user_auth.error(409,"仅已发布内容可归档："+item.slug)
                if data.action=="publish":
                    verify_links(data.kind,parse_json(row["draft_json"]))
                checked.append(row)
            results=[]
            for row in checked:
                action=data.action;status={"submit":"review","publish":"published","archive":"archived"}[action]
                published=row["draft_json"] if action=="publish" else None if action=="archive" else row["published_json"]
                updated=db.execute("""UPDATE atlas_cms_entries
                    SET status=?,published_json=?,published_at=?,published_by=?,revision=?,updated_by=?,updated_at=?
                    WHERE kind=? AND slug=? AND revision=?""",
                    (status,published,now if action=="publish" else row["published_at"],
                     uid if action=="publish" else row["published_by"],row["revision"]+1,uid,now,
                     data.kind,row["slug"],row["revision"]))
                if updated.rowcount!=1:user_auth.error(409,"批量版本冲突："+row["slug"])
                log_change(db,{**row,"revision":row["revision"]+1},action,uid)
                results.append({"slug":row["slug"],"revision":row["revision"]+1,"status":status})
        invalidate()
        return {"ok":True,"results":results}

    @app.get("/api/admin/content", include_in_schema=False)
    def list_entries(request:Request,kind:KIND="site",q:str="",status:str=""):
        require_admin(request)
        ensure_cms()
        bases=base_maps()[KIND_CATALOG[kind]]
        with user_auth.db() as db:
            rows=db.all("SELECT kind,slug,draft_json,published_json,status,revision,updated_at,published_at FROM atlas_cms_entries WHERE kind=?",(kind,))
        overlay={r["slug"]:r for r in rows}
        ids=list(dict.fromkeys(list(bases.keys())+list(overlay.keys())))
        items=[]
        for slug in ids:
            row=overlay.get(slug)
            if row:
                p=parse_json(row["draft_json"]);label=p.get("name") or p.get("title") or slug
                state=row["status"];revision=row["revision"];when=row["updated_at"]
            else:
                p=bases[slug];label=p.get("name") or p.get("title") or slug
                state="source";revision=0;when=""
            if status and state!=status:continue
            if q and q.casefold() not in (" ".join([slug,str(label),str(p.get("sector",p.get("category","")))]).casefold()):continue
            items.append({"kind":kind,"slug":slug,"label":str(label)[:160],"status":state,
                "revision":revision,"updated_at":when,"url":KIND_ROUTE[kind]+slug,
                "sector":str(p.get("sector") or p.get("category") or p.get("family") or "")[:100],
                "source":"cms" if row else "repository"})
        items.sort(key=lambda x:(x["status"]=="source",x["label"].casefold()))
        return {"kind":kind,"total":len(items),"items":items}

    @app.get("/api/admin/content/export",include_in_schema=False)
    def export_content(request:Request):
        require_admin(request)
        ensure_cms()
        with user_auth.db() as db:
            entries=db.all("SELECT * FROM atlas_cms_entries ORDER BY kind,slug")
            history=db.all("SELECT * FROM atlas_cms_history ORDER BY created_at")
        return JSONResponse({"version":1,"exported_at":utc_now(),"entries":entries,
             "history":history,"note":"仅 CMS 内容快照，不含登录凭证或用户私人数据。"},
            headers={"Cache-Control":"no-store","Content-Disposition":'attachment; filename="atlas-cms-export.json"'})

    @app.get("/api/admin/content/{kind}/{slug}",include_in_schema=False)
    def content_detail(kind:KIND,slug:str,request:Request):
        session=require_admin(request)
        return cms_item(kind,slug,session)

    @app.post("/api/admin/content",include_in_schema=False,status_code=201)
    def create_content(data:Create,request:Request):
        session=require_admin(request,mutate=True)
        slug=data.slug
        if not SLUG.fullmatch(slug):user_auth.error(422,"无效 URL 标识。")
        payload=cleaned(data.kind,slug,data.payload)
        if base_item(data.kind,slug):user_auth.error(409,"资源已存在，请打开它并编辑。")
        ensure_cms()
        with user_auth.db() as db:
            if db.one("SELECT slug FROM atlas_cms_entries WHERE kind=? AND slug=?",(data.kind,slug)):
                user_auth.error(409,"已存在相同的 URL 标识。")
            now=utc_now();uid=session["user_id"]
            data_json=json.dumps(payload,ensure_ascii=False)
            db.execute("""INSERT INTO atlas_cms_entries
                (kind,slug,draft_json,published_json,status,revision,created_by,updated_by,created_at,updated_at)
                VALUES(?,?,?,NULL,'draft',1,?,?,?,?)""",
                (data.kind,slug,data_json,uid,uid,now,now))
            log_change(db,{"kind":data.kind,"slug":slug,"revision":1,"draft_json":data_json},"create",uid)
        return {"ok":True,"revision":1,"status":"draft"}

    @app.put("/api/admin/content/{kind}/{slug}",include_in_schema=False)
    def save_draft(kind:KIND,slug:str,data:Draft,request:Request):
        session=require_admin(request,mutate=True)
        payload=cleaned(kind,slug,data.payload)
        ensure_cms();uid=session["user_id"];now=utc_now()
        encoded=json.dumps(payload,ensure_ascii=False)
        with user_auth.db() as db:
            old=db.one("SELECT * FROM atlas_cms_entries WHERE kind=? AND slug=?",(kind,slug))
            if old:
                if old["revision"]!=data.expected_revision:user_auth.error(409,"内容已被其他人修改，请刷新后重试。")
                revision=old["revision"]+1
                # A live published snapshot remains live while its next draft
                # is edited. No unreviewed change becomes public.
                result=db.execute("""UPDATE atlas_cms_entries
                   SET draft_json=?,status='draft',revision=?,updated_by=?,updated_at=?
                   WHERE kind=? AND slug=? AND revision=?""",
                   (encoded,revision,uid,now,kind,slug,data.expected_revision))
                if result.rowcount!=1:user_auth.error(409,"版本冲突，请刷新。")
            else:
                if data.expected_revision!=0:user_auth.error(409,"版本冲突，请刷新。")
                if not base_item(kind,slug):user_auth.error(404,"未找到需要编辑的内容，请先新建。")
                revision=1
                db.execute("""INSERT INTO atlas_cms_entries
                    (kind,slug,draft_json,published_json,status,revision,created_by,updated_by,created_at,updated_at)
                    VALUES(?,?,?,NULL,'draft',1,?,?,?,?)""",
                    (kind,slug,encoded,uid,uid,now,now))
            log_change(db,{"kind":kind,"slug":slug,"revision":revision,"draft_json":encoded},"save",uid)
        return {"ok":True,"status":"draft","revision":revision}

    def transition(kind,slug,expected,action,session):
        ensure_cms();uid=session["user_id"];now=utc_now()
        with user_auth.db() as db:
            row=db.one("SELECT * FROM atlas_cms_entries WHERE kind=? AND slug=?",(kind,slug))
            if not row:user_auth.error(404,"尚未创建内容草稿。")
            if row["revision"]!=expected:user_auth.error(409,"版本已更新，请重新打开内容。")
            if action=="submit":
                if row["status"]!="draft":user_auth.error(409,"只有草稿可以提交审核。")
                next_status="review";published_json=row["published_json"];published_at=row["published_at"];published_by=row["published_by"]
            elif action=="publish":
                if row["status"]!="review":user_auth.error(409,"内容必须先提交审核，才能发布。")
                draft=parse_json(row["draft_json"])
                verify_links(kind,draft)
                next_status="published";published_json=row["draft_json"];published_at=now;published_by=uid
            elif action=="archive":
                if row["status"]!="published" and row["published_json"] is None:user_auth.error(409,"该内容尚未发布。")
                next_status="archived";published_json=None;published_at=row["published_at"];published_by=row["published_by"]
            else:user_auth.error(400,"不支持的操作。")
            revision=row["revision"]+1
            result=db.execute("""UPDATE atlas_cms_entries
              SET status=?,published_json=?,published_at=?,published_by=?,revision=?,updated_by=?,updated_at=?
              WHERE kind=? AND slug=? AND revision=?""",
              (next_status,published_json,published_at,published_by,revision,uid,now,kind,slug,expected))
            if result.rowcount!=1:user_auth.error(409,"版本已改变。")
            log_change(db,{"kind":kind,"slug":slug,"revision":revision,"draft_json":row["draft_json"]},action,uid)
        invalidate()
        return {"ok":True,"status":next_status,"revision":revision}

    @app.post("/api/admin/content/{kind}/{slug}/submit",include_in_schema=False)
    def submit_content(kind:KIND,slug:str,data:Change,request:Request):
        session=require_admin(request,mutate=True)
        return transition(kind,slug,data.expected_revision,"submit",session)

    @app.post("/api/admin/content/{kind}/{slug}/publish",include_in_schema=False)
    def publish_content(kind:KIND,slug:str,data:Change,request:Request):
        session=require_admin(request,mutate=True)
        return transition(kind,slug,data.expected_revision,"publish",session)

    @app.post("/api/admin/content/{kind}/{slug}/archive",include_in_schema=False)
    def archive_content(kind:KIND,slug:str,data:Change,request:Request):
        session=require_admin(request,mutate=True)
        return transition(kind,slug,data.expected_revision,"archive",session)

    @app.post("/api/admin/content/{kind}/{slug}/restore",include_in_schema=False)
    def restore_revision(kind:KIND,slug:str,data:Restore,request:Request):
        session=require_admin(request,mutate=True)
        ensure_cms();now=utc_now();uid=session["user_id"]
        with user_auth.db() as db:
            old=db.one("SELECT * FROM atlas_cms_entries WHERE kind=? AND slug=?",(kind,slug))
            if not old:user_auth.error(404,"内容不存在。")
            if old["revision"]!=data.expected_revision:user_auth.error(409,"版本冲突，请刷新。")
            rev=db.one("SELECT snapshot_json FROM atlas_cms_history WHERE kind=? AND slug=? AND revision=?",
                       (kind,slug,data.revision))
            if not rev:user_auth.error(404,"没有找到该历史版本。")
            restored=cleaned(kind,slug,parse_json(rev["snapshot_json"]))
            encoded=json.dumps(restored,ensure_ascii=False)
            revision=old["revision"]+1
            result=db.execute("""UPDATE atlas_cms_entries
                SET draft_json=?,status='draft',revision=?,updated_by=?,updated_at=?
                WHERE kind=? AND slug=? AND revision=?""",
                (encoded,revision,uid,now,kind,slug,data.expected_revision))
            if result.rowcount!=1:user_auth.error(409,"版本冲突。")
            log_change(db,{"kind":kind,"slug":slug,"revision":revision,"draft_json":encoded},"restore",uid)
        return {"ok":True,"status":"draft","revision":revision}
