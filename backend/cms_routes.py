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

from app import user_auth, admin_routes, seo_routes, cms_access

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
    """CREATE INDEX IF NOT EXISTS atlas_cms_media_created ON atlas_cms_media(created_at)""",
    """CREATE TABLE IF NOT EXISTS atlas_cms_media_meta (
       media_id TEXT PRIMARY KEY REFERENCES atlas_cms_media(id) ON DELETE CASCADE,
       alt_text TEXT NOT NULL DEFAULT '',
       caption TEXT NOT NULL DEFAULT '',
       updated_by TEXT NOT NULL REFERENCES atlas_users(id),
       updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS atlas_cms_categories (
       id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
       status TEXT NOT NULL CHECK(status IN ('active','deleted')),
       created_by TEXT NOT NULL REFERENCES atlas_users(id),
       updated_by TEXT NOT NULL REFERENCES atlas_users(id),
       created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS atlas_cms_category_history (
       id TEXT PRIMARY KEY, category_id TEXT NOT NULL,
       action TEXT NOT NULL, actor_id TEXT NOT NULL,
       snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS atlas_cms_category_history_cat ON atlas_cms_category_history(category_id,created_at)""",
    """CREATE TABLE IF NOT EXISTS atlas_cms_tags (
       name TEXT PRIMARY KEY, description TEXT NOT NULL,
       status TEXT NOT NULL CHECK(status IN ('active','deleted')),
       created_by TEXT NOT NULL REFERENCES atlas_users(id),
       updated_by TEXT NOT NULL REFERENCES atlas_users(id),
       created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS atlas_cms_tag_history (
       id TEXT PRIMARY KEY, tag_name TEXT NOT NULL,
       action TEXT NOT NULL, actor_id TEXT NOT NULL,
       snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS atlas_cms_review_notes (
       kind TEXT NOT NULL, slug TEXT NOT NULL, revision INTEGER NOT NULL,
       actor_id TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
       PRIMARY KEY(kind,slug,revision)
    )""",
    """CREATE TABLE IF NOT EXISTS atlas_cms_schedules(
       kind TEXT NOT NULL,slug TEXT NOT NULL,revision INTEGER NOT NULL,
       publish_at TEXT NOT NULL,status TEXT NOT NULL,
       created_by TEXT NOT NULL,created_at TEXT NOT NULL,
       updated_at TEXT NOT NULL,error TEXT NOT NULL DEFAULT '',
       PRIMARY KEY(kind,slug)
    )""",
    """CREATE INDEX IF NOT EXISTS atlas_cms_schedule_due ON atlas_cms_schedules(status,publish_at)""",
    """CREATE TABLE IF NOT EXISTS atlas_cms_schedule_history(
       id TEXT PRIMARY KEY,kind TEXT NOT NULL,slug TEXT NOT NULL,
       action TEXT NOT NULL,actor_id TEXT NOT NULL,
       details TEXT NOT NULL,created_at TEXT NOT NULL
    )"""
]

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def require_admin(request: Request, mutate=False, permission=None):
    session = user_auth.required(request)
    cms_access.require(session,permission or ("edit" if mutate else "view"))
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
    try:
        from app.cms_schedule import publish_due
        publish_due()
    except Exception:
        # The public catalog must remain available even if the scheduler fails.
        pass
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
        out["categories"]=article_categories()
    return out

def base_article_categories():
    data=seo_routes.read_json(seo_routes.STATIC/"assets"/"articles.json",{})
    return [x for x in data.get("categories",[]) if isinstance(x,dict) and x.get("id")]

def merge_article_categories(base, overrides):
    """Apply admin taxonomy changes while keeping original category ordering."""
    ordered={x["id"]:dict(x) for x in base}
    for row in overrides:
        key=row["id"]
        if row["status"]=="deleted":
            ordered.pop(key,None)
        else:
            ordered[key]={"id":key,"name":row["name"],"description":row["description"]}
    return list(ordered.values())

def article_categories():
    source=base_article_categories()
    try:
        ensure_cms()
        with user_auth.db() as db:
            changes=db.all("SELECT id,name,description,status FROM atlas_cms_categories ORDER BY created_at,id")
        return merge_article_categories(source,changes)
    except Exception:
        return source

def category_usage(category_id,base_articles,stored_rows):
    """Count unique content records using the category, including unpublished changes."""
    used={slug for slug,p in base_articles.items() if p.get("category")==category_id}
    for row in stored_rows:
        for column in ("draft_json","published_json"):
            try:
                payload=parse_json(row[column]) if row[column] else None
            except (TypeError,ValueError):
                continue
            if isinstance(payload,dict) and payload.get("category")==category_id:
                used.add(row["slug"])
    return len(used)

def normalize_editorial_tag(name):
    if not isinstance(name,str):return ""
    name=name.strip()
    if not name or len(name)>32 or any(ord(ch)<32 for ch in name) or "<" in name or ">" in name:
        return ""
    return name

def article_tag_usage(tag,base_articles,stored_rows):
    """Distinct content resources using the exact tag across snapshots."""
    matching=set()
    target=tag.casefold()
    for slug,payload in base_articles.items():
        if isinstance(payload,dict) and any(
            isinstance(v,str) and v.strip().casefold()==target
            for v in payload.get("tags",[]) if isinstance(payload.get("tags",[]),list)
        ):matching.add(slug)
    for row in stored_rows:
        for field in ("draft_json","published_json"):
            try:p=parse_json(row[field]) if row[field] else None
            except (TypeError,ValueError):continue
            if isinstance(p,dict) and isinstance(p.get("tags"),list) and any(
                isinstance(v,str) and v.strip().casefold()==target for v in p["tags"]
            ):matching.add(row["slug"])
    return len(matching)

def merge_editorial_tags(base_articles,stored_rows,overrides):
    """Referenced tags and manually curated tags, excluding soft-deleted unused tags."""
    labels={}
    for article in base_articles.values():
        for t in article.get("tags",[]) if isinstance(article.get("tags"),list) else []:
            label=normalize_editorial_tag(t)
            if label:labels.setdefault(label.casefold(),label)
    for row in stored_rows:
        for field in ("draft_json","published_json"):
            try:article=parse_json(row[field]) if row[field] else None
            except (TypeError,ValueError):continue
            if not isinstance(article,dict):continue
            for t in article.get("tags",[]) if isinstance(article.get("tags"),list) else []:
                label=normalize_editorial_tag(t)
                if label:labels.setdefault(label.casefold(),label)
    result={}
    for key,label in labels.items():
        result[key]={"name":label,"description":"","source":"content"}
    for row in overrides:
        key=row["name"].casefold()
        if row["status"]=="deleted":
            if key not in labels:result.pop(key,None)
        else:
            result[key]={"name":row["name"],"description":row["description"],"source":"cms"}
    return sorted(({**value,"usage":article_tag_usage(value["name"],base_articles,stored_rows)}
                   for value in result.values()),key=lambda x:(-x["usage"],x["name"].casefold()))

def all_editorial_tags():
    ensure_cms()
    base=base_maps()["articles"]
    with user_auth.db() as db:
        rows=db.all("SELECT slug,draft_json,published_json FROM atlas_cms_entries WHERE kind='article'")
        overrides=db.all("SELECT name,description,status,created_at,updated_at FROM atlas_cms_tags ORDER BY created_at,name")
    return merge_editorial_tags(base,rows,overrides)

ARTICLE_BLOCK_TYPES={"paragraph","heading","quote","callout","list","image","table","link"}
def validate_article_blocks(blocks):
    """Validate structured article blocks without changing legacy article payloads."""
    if not isinstance(blocks,list) or len(blocks)>70:
        user_auth.error(422,"每章最多 70 个正文块。")
    for block in blocks:
        if not isinstance(block,dict) or block.get("type") not in ARTICLE_BLOCK_TYPES:
            user_auth.error(422,"文章包含不支持的正文块类型。")
        kind=block["type"]
        if kind in ("paragraph","heading","quote","callout","link"):
            value=block.get("text","")
            if not isinstance(value,str) or len(value)>12000:
                user_auth.error(422,"正文块文字长度超出限制。")
        if kind=="list":
            values=block.get("items",[])
            if not isinstance(values,list) or len(values)>60 or any(
                not isinstance(text,str) or len(text)>1800 for text in values
            ):user_auth.error(422,"列表块格式无效。")
        if kind=="table":
            rows=block.get("rows",[])
            if not isinstance(rows,list) or len(rows)>30 or any(
                not isinstance(row,list) or len(row)>8 or any(
                    not isinstance(cell,str) or len(cell)>1500 for cell in row
                ) for row in rows
            ):user_auth.error(422,"表格块最多 30 行、每行 8 列。")
        if kind=="image":
            src=block.get("src","")
            if src and (not isinstance(src,str) or not re.fullmatch(
                r"/api/media/[0-9a-f-]{36}",src
            )):user_auth.error(422,"图片块必须选择站内媒体。")
            if any(not isinstance(block.get(k,""),str) or len(block.get(k,""))>240 for k in ("alt","caption")):
                user_auth.error(422,"图片替代文字或说明超过限制。")
        if kind=="link":
            uri=block.get("url","")
            if uri and (not isinstance(uri,str) or len(uri)>500 or
                urlparse(uri).scheme not in ("https","http") or not urlparse(uri).netloc):
                user_auth.error(422,"链接块需要有效的 http(s) 地址。")

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
        for metadata,max_chars in (("seo_title",100),("seo_description",300)):
            v=result.get(metadata,"")
            if v is not None and (not isinstance(v,str) or len(v)>max_chars):
                user_auth.error(422,metadata+" 长度不合法。")
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
            if "blocks" in s:
                validate_article_blocks(s["blocks"])
            for text_field,maximum in (("paragraphs",80),("bullets",60)):
                entries=s.get(text_field,[])
                if not isinstance(entries,list) or len(entries)>maximum or any(
                    not isinstance(entry,str) or len(entry)>12000 for entry in entries
                ):
                    user_auth.error(422,"章节 "+text_field+" 数据格式无效或过长。")
            if s.get("callout") is not None and (not isinstance(s["callout"],str) or len(s["callout"])>2000):
                user_auth.error(422,"章节提示内容格式无效或过长。")
            if s.get("image") and (not isinstance(s["image"],str) or
                                  not re.fullmatch(r"/api/media/[0-9a-f-]{36}",s["image"])):
                user_auth.error(422,"章节图片只能从媒体资源库选择。")
            if s.get("image_caption") and (not isinstance(s["image_caption"],str) or len(s["image_caption"])>240):
                user_auth.error(422,"图片说明不可超过 240 字。")
    for field in ("screenshot_url","source_capture"):
        if field in result:
            value=result[field]
            allowed = (re.fullmatch(r"/screenshots/[a-zA-Z0-9_./-]{1,200}",value) or
                       (field=="screenshot_url" and re.fullmatch(r"/api/media/[0-9a-f-]{36}",value))) if isinstance(value,str) else None
            if not isinstance(value,str) or (value and not allowed):
                user_auth.error(422,"截图只能引用站内截图或已上传的媒体图片。")
            if ".." in value:user_auth.error(422,"截图路径不合法。")
    if kind=="site" and "gallery" in result:
        gallery=result["gallery"]
        if not isinstance(gallery,list) or len(gallery)>16:
            user_auth.error(422,"网站截图最多可添加 16 张。")
        seen=set()
        for screenshot in gallery:
            if not isinstance(screenshot,dict):
                user_auth.error(422,"页面截图格式不正确。")
            url=screenshot.get("url")
            label=screenshot.get("label","")
            if not isinstance(url,str) or not isinstance(label,str) or len(label)>80:
                user_auth.error(422,"页面截图标题或地址不正确。")
            valid=(re.fullmatch(r"/screenshots/[a-zA-Z0-9_./-]{1,200}",url) and ".." not in url) or \
                  re.fullmatch(r"/api/media/[0-9a-f-]{36}",url)
            if not valid or url in seen:
                user_auth.error(422,"页面截图只能选择站内图片，且不能重复。")
            seen.add(url)
    if kind=="pattern" and "modules" in result:
        if not isinstance(result["modules"],list) or len(result["modules"])>30 or any(not isinstance(x,str) or not SLUG.fullmatch(x) for x in result["modules"]):
            user_auth.error(422,"关联模块 ID 格式无效。")
    return result

def verify_links(kind,payload):
    current=seo_routes.catalog()
    if kind=="module" and payload["site_id"] not in current["sites"]:
        user_auth.error(422,"关联的网站不存在或尚未发布。")
    if kind=="article" and payload.get("category") not in {x["id"] for x in article_categories()}:
        user_auth.error(422,"文章分类未创建或已停用，请先在分类管理中维护。")
    if kind=="article" and payload.get("cover_site") and payload["cover_site"] not in current["sites"]:
        user_auth.error(422,"封面关联网站尚未发布。")
    if kind in ("site","module"):
        references=[payload.get("screenshot_url","")]
        if kind=="site":
            references += [shot.get("url","") for shot in payload.get("gallery",[])
                           if isinstance(shot,dict)]
        media_ids={u.rsplit("/",1)[-1] for u in references
                   if isinstance(u,str) and u.startswith("/api/media/")}
        if media_ids:
            ensure_cms()
            with user_auth.db() as db:
                for media_id in media_ids:
                    if not db.one("SELECT id FROM atlas_cms_media WHERE id=?",(media_id,)):
                        user_auth.error(422,"页面截图已不存在，请重新从媒体库选择。")
    if kind=="article":
        referenced=[payload.get("cover_image","")]
        referenced += [s.get("image","") for s in payload.get("sections",[]) if isinstance(s,dict)]
        referenced += [block.get("src","") for section in payload.get("sections",[])
                       if isinstance(section,dict) for block in section.get("blocks",[])
                       if isinstance(block,dict) and block.get("type")=="image"]
        referenced=[v.rsplit("/",1)[-1] for v in referenced if v]
        if referenced:
            ensure_cms()
            with user_auth.db() as db:
                for media_id in set(referenced):
                    if not db.one("SELECT id FROM atlas_cms_media WHERE id=?",(media_id,)):
                        user_auth.error(422,"文章引用了已删除的图片，请从媒体库重新选择。")
    if kind=="article":
        for chapter in payload.get("sections",[]):
            if "blocks" in chapter:
                valid_text=any(
                    b.get("type") in ("paragraph","heading","quote","callout","list","table")
                    and (str(b.get("text","")).strip() or b.get("items") or b.get("rows"))
                    for b in chapter.get("blocks",[]) if isinstance(b,dict)
                )
                if not valid_text:user_auth.error(422,"发布前每章至少需要一个有效正文或列表块。")
            else:
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

class RejectDecision(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=4,max_length=400)

def validate_review_reason(reason):
    if not isinstance(reason,str) or len(reason.strip())<4:
        user_auth.error(422,"退回原因至少需要 4 个字符。")

class Restore(BaseModel):
    expected_revision: int = Field(ge=0)
    revision: int = Field(ge=1)

class CategoryData(BaseModel):
    id: str = Field(min_length=2,max_length=48,pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1,max_length=80)
    description: str = Field(default="",max_length=400)

def validate_category_data(data:CategoryData):
    if len(data.id)>48 or not SLUG.fullmatch(data.id):
        user_auth.error(422,"分类 ID 只能使用小写字母、数字和短横线。")
    if not data.name.strip():
        user_auth.error(422,"分类显示名称不能为空。")

class TagData(BaseModel):
    name: str = Field(min_length=1,max_length=32)
    description: str = Field(default="",max_length=400)

def validate_tag_data(data:TagData):
    if not normalize_editorial_tag(data.name) or not data.name.strip():
        user_auth.error(422,"标签名称必须为 1–32 个有效字符。")

class MediaUpload(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    mime: Literal["image/jpeg","image/png","image/webp"]
    content: str = Field(min_length=16,max_length=2800000)

class MediaMetadata(BaseModel):
    alt_text: str = Field(default="",max_length=240)
    caption: str = Field(default="",max_length=320)

class MediaBulkDelete(BaseModel):
    ids: list[str] = Field(min_length=1,max_length=20)

class BulkItem(BaseModel):
    slug: str = Field(min_length=1,max_length=111)
    expected_revision: int = Field(ge=1)

class BulkChange(BaseModel):
    kind: KIND
    action: Literal["submit","publish","archive"]
    items: list[BulkItem] = Field(min_length=1,max_length=20)


def invalidate_schedule(db,kind,slug):
    db.execute("""UPDATE atlas_cms_schedules
       SET status='stale',error='内容版本已更改，原排期不再有效。',updated_at=?
       WHERE kind=? AND slug=? AND status='pending'""",
       (utc_now(),kind,slug))

def log_change(db,row,action,uid):
    db.execute("""INSERT INTO atlas_cms_history(id,kind,slug,revision,action,actor_id,created_at,snapshot_json)
               VALUES(?,?,?,?,?,?,?,?)""",
               (str(uuid.uuid4()),row["kind"],row["slug"],row["revision"],action,uid,utc_now(),row["draft_json"]))

def base_item(kind,slug):
    return base_maps()[KIND_CATALOG[kind]].get(slug)

def published_baseline_for_editor(kind,slug,row,base):
    """The real public baseline for review and diff, including archive tombstones.

    A source-derived draft has no published_json until its first release, but
    the original file-backed record remains visible. Once archived, the history
    tombstone prevents the original record from being presented as public.
    """
    if not row:return base
    if row["status"]=="archived":return None
    if row["published_json"]:return parse_json(row["published_json"])
    if not base:return None
    with user_auth.db() as db:
        archived=db.one("""SELECT 1 AS archived FROM atlas_cms_history
                           WHERE kind=? AND slug=? AND action='archive' LIMIT 1""",
                        (kind,slug))
    return None if archived else base

def cms_item(kind,slug,session):
    ensure_cms()
    with user_auth.db() as db:
        row=db.one("SELECT * FROM atlas_cms_entries WHERE kind=? AND slug=?",(kind,slug))
        history=db.all("""SELECT h.revision,h.action,h.actor_id,h.created_at,
                       COALESCE(n.reason,'') AS reason
                       FROM atlas_cms_history h LEFT JOIN atlas_cms_review_notes n
                       ON n.kind=h.kind AND n.slug=h.slug AND n.revision=h.revision
                       WHERE h.kind=? AND h.slug=?
                       ORDER BY h.revision DESC LIMIT 35""",(kind,slug))
        schedule=db.one("""SELECT publish_at,status,revision,error,created_by,
                             updated_at FROM atlas_cms_schedules
                           WHERE kind=? AND slug=?""",(kind,slug))
    base=base_item(kind,slug)
    if not row and not base:user_auth.error(404,"内容不存在。")
    published=published_baseline_for_editor(kind,slug,row,base)
    return {
        "kind":kind,"slug":slug,"source":"cms" if row else "repository",
        "status":row["status"] if row else "source",
        "revision":row["revision"] if row else 0,
        "payload":parse_json(row["draft_json"]) if row else base,
        "published":published,
        "published_at":row["published_at"] if row else None,
        "history":history,"schedule":schedule
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

    @app.get("/api/admin/tags",include_in_schema=False)
    def list_tags(request:Request):
        require_admin(request)
        return {"items":all_editorial_tags()}

    @app.post("/api/admin/tags",include_in_schema=False,status_code=201)
    def create_tag(data:TagData,request:Request):
        session=require_admin(request,mutate=True);ensure_cms()
        validate_tag_data(data)
        name=data.name.strip()
        if name.casefold() in {v["name"].casefold() for v in all_editorial_tags()}:
            user_auth.error(409,"该标签已经存在，您可以直接编辑说明。")
        with user_auth.db() as db:
            if db.one("SELECT name FROM atlas_cms_tags WHERE LOWER(name)=LOWER(?)",(name,)):
                user_auth.error(409,"该标签已登记或已停用。")
            now=utc_now();uid=session["user_id"]
            db.execute("""INSERT INTO atlas_cms_tags
                (name,description,status,created_by,updated_by,created_at,updated_at)
                VALUES(?,?,'active',?,?,?,?)""",
                (name,data.description.strip(),uid,uid,now,now))
            db.execute("""INSERT INTO atlas_cms_tag_history
                (id,tag_name,action,actor_id,snapshot_json,created_at)
                VALUES(?,?,?,?,?,?)""",
                (str(uuid.uuid4()),name,"create",uid,json.dumps(data.dict(),ensure_ascii=False),now))
        return {"ok":True,"name":name}

    @app.put("/api/admin/tags/{tag_name}",include_in_schema=False)
    def update_tag(tag_name:str,data:TagData,request:Request):
        session=require_admin(request,mutate=True);ensure_cms()
        validate_tag_data(data)
        if tag_name.casefold()!=data.name.strip().casefold():
            user_auth.error(422,"标签名称不可直接更改。请新建标签，再调整引用文章。")
        if tag_name.casefold() not in {v["name"].casefold() for v in all_editorial_tags()}:
            user_auth.error(404,"标签不存在。")
        with user_auth.db() as db:
            now=utc_now();uid=session["user_id"]
            db.execute("""INSERT INTO atlas_cms_tags
                (name,description,status,created_by,updated_by,created_at,updated_at)
                VALUES(?,?,'active',?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET description=excluded.description,
                  status='active',updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
                (data.name.strip(),data.description.strip(),uid,uid,now,now))
            db.execute("""INSERT INTO atlas_cms_tag_history
                (id,tag_name,action,actor_id,snapshot_json,created_at)
                VALUES(?,?,?,?,?,?)""",
                (str(uuid.uuid4()),tag_name,"edit",uid,json.dumps(data.dict(),ensure_ascii=False),now))
        return {"ok":True,"name":tag_name}

    @app.delete("/api/admin/tags/{tag_name}",include_in_schema=False)
    def delete_tag(tag_name:str,request:Request):
        session=require_admin(request,mutate=True);ensure_cms()
        current=all_editorial_tags()
        item=next((x for x in current if x["name"].casefold()==tag_name.casefold()),None)
        if not item:user_auth.error(404,"标签不存在。")
        if item["usage"]>0:user_auth.error(409,"标签仍被文章或草稿使用，请先修改引用。")
        with user_auth.db() as db:
            now=utc_now();uid=session["user_id"]
            db.execute("""INSERT INTO atlas_cms_tags
                (name,description,status,created_by,updated_by,created_at,updated_at)
                VALUES(?,?,'deleted',?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET status='deleted',
                  updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
                (tag_name,"",uid,uid,now,now))
            db.execute("""INSERT INTO atlas_cms_tag_history
                (id,tag_name,action,actor_id,snapshot_json,created_at)
                VALUES(?,?,?,?,?,?)""",
                (str(uuid.uuid4()),tag_name,"delete",uid,json.dumps({"name":tag_name},ensure_ascii=False),now))
        return {"ok":True,"name":tag_name}

    @app.get("/api/admin/categories",include_in_schema=False)
    def list_categories(request:Request):
        require_admin(request);ensure_cms()
        base=base_article_categories()
        with user_auth.db() as db:
            overrides=db.all("SELECT id,name,description,status,created_at,updated_at FROM atlas_cms_categories ORDER BY created_at,id")
            entries=db.all("SELECT slug,draft_json,published_json FROM atlas_cms_entries WHERE kind='article'")
        names=merge_article_categories(base,overrides)
        base_ids={x["id"] for x in base}
        by_id={x["id"]:x for x in overrides}
        existing=base_maps()["articles"]
        return {"items":[{**item,"source":"repository" if item["id"] in base_ids else "cms",
                "usage":category_usage(item["id"],existing,entries),
                "updated_at":by_id.get(item["id"],{}).get("updated_at","")}
                for item in names]}

    @app.post("/api/admin/categories",include_in_schema=False,status_code=201)
    def create_category(data:CategoryData,request:Request):
        session=require_admin(request,mutate=True);ensure_cms()
        validate_category_data(data)
        if data.id in {x["id"] for x in base_article_categories()}:
            user_auth.error(409,"该分类 ID 已经存在，可直接编辑名称。")
        with user_auth.db() as db:
            if db.one("SELECT id FROM atlas_cms_categories WHERE id=?",(data.id,)):
                user_auth.error(409,"该分类 ID 已占用。")
            now=utc_now()
            db.execute("""INSERT INTO atlas_cms_categories
                (id,name,description,status,created_by,updated_by,created_at,updated_at)
                VALUES(?,?,?,'active',?,?,?,?)""",
                (data.id,data.name.strip(),data.description.strip(),session["user_id"],session["user_id"],now,now))
            db.execute("INSERT INTO atlas_cms_category_history(id,category_id,action,actor_id,snapshot_json,created_at) VALUES(?,?,?,?,?,?)",
                (str(uuid.uuid4()),data.id,"create",session["user_id"],json.dumps(data.dict(),ensure_ascii=False),now))
        return {"ok":True,"id":data.id}

    @app.put("/api/admin/categories/{category_id}",include_in_schema=False)
    def edit_category(category_id:str,data:CategoryData,request:Request):
        session=require_admin(request,mutate=True);ensure_cms()
        validate_category_data(data)
        if category_id!=data.id:user_auth.error(422,"分类 ID 不可更改。")
        if category_id not in {x["id"] for x in base_article_categories()}:
            with user_auth.db() as db:
                if not db.one("SELECT id FROM atlas_cms_categories WHERE id=?",(category_id,)):
                    user_auth.error(404,"分类不存在。")
        with user_auth.db() as db:
            now=utc_now()
            db.execute("""INSERT INTO atlas_cms_categories
                (id,name,description,status,created_by,updated_by,created_at,updated_at)
                VALUES(?,?,?,'active',?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,description=excluded.description,status='active',
                updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
                (category_id,data.name.strip(),data.description.strip(),session["user_id"],session["user_id"],now,now))
            db.execute("INSERT INTO atlas_cms_category_history(id,category_id,action,actor_id,snapshot_json,created_at) VALUES(?,?,?,?,?,?)",
                (str(uuid.uuid4()),category_id,"edit",session["user_id"],json.dumps(data.dict(),ensure_ascii=False),now))
        return {"ok":True,"id":category_id}

    @app.delete("/api/admin/categories/{category_id}",include_in_schema=False)
    def remove_category(category_id:str,request:Request):
        session=require_admin(request,mutate=True);ensure_cms()
        base={x["id"] for x in base_article_categories()}
        with user_auth.db() as db:
            old=db.one("SELECT id FROM atlas_cms_categories WHERE id=?",(category_id,))
            if category_id not in base and not old:user_auth.error(404,"分类不存在。")
            entries=db.all("SELECT slug,draft_json,published_json FROM atlas_cms_entries WHERE kind='article'")
            if category_usage(category_id,base_maps()["articles"],entries):
                user_auth.error(409,"分类仍被文章或草稿引用，请先调整这些文章的分类。")
            now=utc_now()
            db.execute("""INSERT INTO atlas_cms_categories
                (id,name,description,status,created_by,updated_by,created_at,updated_at)
                VALUES(?,?,?,'deleted',?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                status='deleted',updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
                (category_id,category_id,"",session["user_id"],session["user_id"],now,now))
            db.execute("INSERT INTO atlas_cms_category_history(id,category_id,action,actor_id,snapshot_json,created_at) VALUES(?,?,?,?,?,?)",
                (str(uuid.uuid4()),category_id,"delete",session["user_id"],json.dumps({"id":category_id}),now))
        return {"ok":True,"id":category_id}

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
                values={x["id"] for x in article_categories()}
            result[kind]=sorted(x for x in values if x)[:120]
        tag_counts={}
        for article in current["articles"].values():
            if not isinstance(article,dict):continue
            for tag in article.get("tags",[]):
                if not isinstance(tag,str) or not tag.strip() or len(tag)>32:continue
                tag_counts[tag.strip()]=tag_counts.get(tag.strip(),0)+1
        try:
            common_tags=[x["name"] for x in all_editorial_tags()][:40]
        except Exception:
            common_tags=sorted(tag_counts,key=lambda x:(-tag_counts[x],x))[:40]
        return {"categories":result,"article_tags":common_tags}

    @app.get("/api/admin/media",include_in_schema=False)
    def media_list(request:Request,q:str="",usage:str="all",file_type:str="all",
                   seo:str="all",offset:int=0,limit:int=150):
        require_admin(request);ensure_cms()
        if len(q)>160 or usage not in ("all","used","unused") or file_type not in ("all","jpeg","png","webp") or seo not in ("all","missing","ready"):
            user_auth.error(422,"媒体搜索条件无效。")
        if not 0<=offset<=100000 or not 1<=limit<=150:
            user_auth.error(422,"媒体分页参数无效。")
        with user_auth.db() as db:
            rows=db.all("SELECT id,file_name,mime_type,byte_size,sha256,created_at FROM atlas_cms_media ORDER BY created_at DESC,id DESC")
            entries=db.all("SELECT kind,slug,draft_json,published_json FROM atlas_cms_entries")
            notes=db.all("SELECT media_id,alt_text,caption,updated_at FROM atlas_cms_media_meta")
        metadata={item["media_id"]:item for item in notes}
        # Count references across drafts AND public snapshots; one content item
        # contributes one usage even if the image appears repeatedly.
        usage_map={}
        for entry in entries:
            identifiers=set()
            for field in ("draft_json","published_json"):
                try:document=parse_json(entry[field]) if entry[field] else {}
                except (TypeError,ValueError):continue
                if not isinstance(document,dict):continue
                media_urls=[document.get("cover_image",""),document.get("screenshot_url","")]
                if isinstance(document.get("gallery"),list):
                    media_urls.extend(shot.get("url","") for shot in document["gallery"] if isinstance(shot,dict))
                if isinstance(document.get("sections"),list):
                    for chapter in document["sections"]:
                        if not isinstance(chapter,dict):continue
                        media_urls.append(chapter.get("image",""))
                        for block in chapter.get("blocks",[]):
                            if isinstance(block,dict) and block.get("type")=="image":
                                media_urls.append(block.get("src",""))
                identifiers.update(u.rsplit("/",1)[-1] for u in media_urls if isinstance(u,str) and
                                   re.fullmatch(r"/api/media/[0-9a-f-]{36}",u))
            for mid in identifiers:
                usage_map.setdefault(mid,[]).append({"kind":entry["kind"],"slug":entry["slug"]})
        search=q.casefold().strip()
        found=[]
        for row in rows:
            media_id=row["id"];info=metadata.get(media_id,{})
            alt_text=info.get("alt_text","");caption=info.get("caption","")
            users=usage_map.get(media_id,[])
            record={**row,"url":"/api/media/"+media_id,
                    "alt_text":alt_text,"caption":caption,"metadata_updated_at":info.get("updated_at"),
                    "seo_status":"ready" if alt_text.strip() else "missing",
                    "usage_count":len(users),"used_by":users[:20]}
            if search and search not in (" ".join([row["file_name"],alt_text,caption]+
                                                    [link["slug"] for link in users])).casefold():continue
            if usage=="used" and not users:continue
            if usage=="unused" and users:continue
            if file_type!="all" and row["mime_type"]!="image/"+("jpeg" if file_type=="jpeg" else file_type):continue
            if seo=="missing" and alt_text.strip():continue
            if seo=="ready" and not alt_text.strip():continue
            found.append(record)
        return {"items":found[offset:offset+limit],"total":len(found),"offset":offset,
                "limit":limit,"has_more":offset+limit<len(found)}

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

    @app.put("/api/admin/media/{media_id}/metadata",include_in_schema=False)
    def update_media_metadata(media_id:str,data:MediaMetadata,request:Request):
        session=require_admin(request,mutate=True,permission="media");ensure_cms()
        try:uuid.UUID(media_id)
        except ValueError:user_auth.error(404,"图片不存在。")
        alt_text=data.alt_text.strip();caption=data.caption.strip()
        with user_auth.db() as db:
            if not db.one("SELECT id FROM atlas_cms_media WHERE id=?",(media_id,)):
                user_auth.error(404,"图片不存在。")
            # Portable SQLite/PostgreSQL upsert. The original image is immutable.
            db.execute("""INSERT INTO atlas_cms_media_meta(media_id,alt_text,caption,updated_by,updated_at)
                       VALUES(?,?,?,?,?)
                       ON CONFLICT(media_id) DO UPDATE SET
                         alt_text=excluded.alt_text,caption=excluded.caption,
                         updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
                       (media_id,alt_text,caption,session["user_id"],utc_now()))
        return {"ok":True,"id":media_id,"alt_text":alt_text,"caption":caption}

    def safely_delete_media(db,ids):
        # Validate ALL requested media first, then delete in one DB transaction.
        if len(set(ids))!=len(ids):
            user_auth.error(422,"批量删除包含重复图片，请重新选择。")
        for media_id in ids:
            try:uuid.UUID(media_id)
            except ValueError:user_auth.error(422,"媒体 ID 不合法。")
        for media_id in ids:
            if not db.one("SELECT id FROM atlas_cms_media WHERE id=?",(media_id,)):
                user_auth.error(404,"有图片已不存在，请刷新列表。")
        refs=db.all("SELECT draft_json,published_json FROM atlas_cms_entries")
        for media_id in ids:
            target="/api/media/"+media_id
            for row in refs:
                if any(target in (row[field] or "") for field in ("draft_json","published_json")):
                    user_auth.error(409,"有图片仍被草稿或公开内容引用。请先替换并发布或归档对应内容，重新检查引用后再删除。")
        for media_id in ids:
            db.execute("DELETE FROM atlas_cms_media_meta WHERE media_id=?",(media_id,))
            db.execute("DELETE FROM atlas_cms_media WHERE id=?",(media_id,))

    @app.post("/api/admin/media/bulk-delete",include_in_schema=False)
    def bulk_delete_media(data:MediaBulkDelete,request:Request):
        require_admin(request,mutate=True,permission="media");ensure_cms()
        with user_auth.db() as db:
            safely_delete_media(db,data.ids)
        return {"ok":True,"deleted":len(data.ids)}

    @app.delete("/api/admin/media/{media_id}",include_in_schema=False)
    def delete_media(media_id:str,request:Request):
        require_admin(request,mutate=True,permission="media");ensure_cms()
        with user_auth.db() as db:
            safely_delete_media(db,[media_id])
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
        session=require_admin(request,mutate=True,
            permission="review" if data.action in ("publish","archive") else "edit")
        ensure_cms()
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
                invalidate_schedule(db,data.kind,row["slug"])
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
        require_admin(request,permission="export")
        ensure_cms()
        with user_auth.db() as db:
            entries=db.all("SELECT * FROM atlas_cms_entries ORDER BY kind,slug")
            history=db.all("SELECT * FROM atlas_cms_history ORDER BY created_at")
            categories=db.all("SELECT id,name,description,status,created_at,updated_at FROM atlas_cms_categories ORDER BY created_at")
            category_history=db.all("SELECT * FROM atlas_cms_category_history ORDER BY created_at")
            tags=db.all("SELECT name,description,status,created_at,updated_at FROM atlas_cms_tags ORDER BY name")
            tag_history=db.all("SELECT * FROM atlas_cms_tag_history ORDER BY created_at")
            review_notes=db.all("SELECT kind,slug,revision,actor_id,reason,created_at FROM atlas_cms_review_notes ORDER BY created_at")
            schedules=db.all("SELECT * FROM atlas_cms_schedules ORDER BY publish_at")
            schedule_history=db.all("SELECT * FROM atlas_cms_schedule_history ORDER BY created_at")
        return JSONResponse({"version":3,"exported_at":utc_now(),"entries":entries,
             "history":history,"categories":categories,"category_history":category_history,
             "tags":tags,"tag_history":tag_history,"review_notes":review_notes,"schedules":schedules,"schedule_history":schedule_history,
             "note":"CMS 内容及分类操作快照，不含账号、用户私人数据或媒体二进制文件。"},
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
            invalidate_schedule(db,kind,slug)
        return {"ok":True,"status":"draft","revision":revision}

    def transition(kind,slug,expected,action,session,reason=''):
        ensure_cms();uid=session["user_id"];now=utc_now()
        with user_auth.db() as db:
            row=db.one("SELECT * FROM atlas_cms_entries WHERE kind=? AND slug=?",(kind,slug))
            if not row:user_auth.error(404,"尚未创建内容草稿。")
            if row["revision"]!=expected:user_auth.error(409,"版本已更新，请重新打开内容。")
            if action=="submit":
                if row["status"]!="draft":user_auth.error(409,"只有草稿可以提交审核。")
                next_status="review";published_json=row["published_json"];published_at=row["published_at"];published_by=row["published_by"]
            elif action=="reject":
                if row["status"]!="review":user_auth.error(409,"只有待审核的内容可退回修改。")
                validate_review_reason(reason)
                next_status="draft"
                published_json=row["published_json"]
                published_at=row["published_at"]
                published_by=row["published_by"]
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
            invalidate_schedule(db,kind,slug)
            if action=="reject":
                db.execute("""INSERT INTO atlas_cms_review_notes
                    (kind,slug,revision,actor_id,reason,created_at) VALUES(?,?,?,?,?,?)""",
                    (kind,slug,revision,uid,reason.strip(),now))
        invalidate()
        return {"ok":True,"status":next_status,"revision":revision}

    @app.post("/api/admin/content/{kind}/{slug}/submit",include_in_schema=False)
    def submit_content(kind:KIND,slug:str,data:Change,request:Request):
        session=require_admin(request,mutate=True)
        return transition(kind,slug,data.expected_revision,"submit",session)

    @app.post("/api/admin/content/{kind}/{slug}/reject",include_in_schema=False)
    def reject_content(kind:KIND,slug:str,data:RejectDecision,request:Request):
        session=require_admin(request,mutate=True,permission="review")
        validate_review_reason(data.reason)
        return transition(kind,slug,data.expected_revision,"reject",session,data.reason)

    @app.post("/api/admin/content/{kind}/{slug}/publish",include_in_schema=False)
    def publish_content(kind:KIND,slug:str,data:Change,request:Request):
        session=require_admin(request,mutate=True,permission="review")
        return transition(kind,slug,data.expected_revision,"publish",session)

    @app.post("/api/admin/content/{kind}/{slug}/archive",include_in_schema=False)
    def archive_content(kind:KIND,slug:str,data:Change,request:Request):
        session=require_admin(request,mutate=True,permission="review")
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
            invalidate_schedule(db,kind,slug)
        return {"ok":True,"status":"draft","revision":revision}
