"""V51.7 · Privacy-minimal real operations analytics for B2B Design Atlas.

Public pages record anonymous aggregate page views and intentional searches.
No IP, cookies, user identifiers, referrer URLs or raw request logs are stored.
All account and bookmark metrics come from existing authenticated application data.
"""
from __future__ import annotations

import hashlib
import re
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, Field

from app import user_auth, admin_routes, seo_routes

ANALYTICS_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS atlas_analytics_daily (
        day TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('page_view','search')),
        bucket TEXT NOT NULL,
        n INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(day,kind,bucket)
    )""",
    """CREATE INDEX IF NOT EXISTS atlas_analytics_daily_by_kind
       ON atlas_analytics_daily(kind,day)"""
]
SCHEMA_LOCK=threading.Lock()
SCHEMA_READY=False
RATE_LOCK=threading.Lock()
RATE={}
VALID_SLUG=re.compile(r"^[a-z0-9][a-z0-9-]{0,110}$")
VALID_GROUPS={"websites":"sites","sections":"modules","patterns":"patterns","insights":"articles"}
SEARCH_PII=re.compile(r"@|https?://|www\.|\d[\d\s()+-]{6,}",re.I)

class PublicEvent(BaseModel):
    type: Literal["page_view","search"]
    path: str=Field(default="/",max_length=180)
    query: str=Field(default="",max_length=90)

def normalize_path(value):
    """Only known public catalog routes; never accept arbitrary URLs or querystrings."""
    if not isinstance(value,str) or not value.startswith("/") or "?" in value or "#" in value:
        return None
    if value=="/":return "/"
    parts=value.strip("/").split("/")
    if len(parts) not in (1,2) or parts[0] not in VALID_GROUPS:return None
    if len(parts)==2 and not VALID_SLUG.fullmatch(parts[1]):return None
    return "/"+"/".join(parts)

def normalize_search(value):
    if not isinstance(value,str):return None
    term=re.sub(r"\s+"," ",value.strip().casefold())
    if not 2<=len(term)<=60 or SEARCH_PII.search(term):return None
    # Preserve short text queries for aggregate rankings, without any personal fields.
    if not re.fullmatch(r"[\w\s\-+./#\u4e00-\u9fff]{2,60}",term,re.UNICODE):return None
    return term

def ensure_analytics():
    global SCHEMA_READY
    if SCHEMA_READY:return
    user_auth.ensure_ready()
    with SCHEMA_LOCK:
        if SCHEMA_READY:return
        with user_auth.db() as conn:
            for statement in ANALYTICS_SCHEMA:conn.execute(statement)
        SCHEMA_READY=True

def permitted(request):
    """Minimal in-process abuse guard; identifiers never reach the database."""
    now=int(time.monotonic()//60)
    host=request.client.host if request.client else "unknown"
    fingerprint=hashlib.sha256((str(now)+"|"+host).encode()).hexdigest()[:24]
    with RATE_LOCK:
        if len(RATE)>5000:RATE.clear()
        key=(now,fingerprint)
        count=RATE.get(key,0)
        if count>=90:return False
        RATE[key]=count+1
        if len(RATE)>300 and len(RATE)%50==0:
            for old in list(RATE):
                if old[0]!=now:RATE.pop(old,None)
    return True

def query_report(days,db,now=None):
    """Database-only aggregate report. No synthetic/filler traffic history."""
    now=now or datetime.now(timezone.utc).date()
    start=now-timedelta(days=days-1)
    cutoff=start.isoformat()
    series=db.all(
        "SELECT day,kind,SUM(n) AS n FROM atlas_analytics_daily "
        "WHERE day>=? GROUP BY day,kind ORDER BY day",
        (cutoff,)
    )
    trends={day.isoformat():{"date":day.isoformat(),"views":0,"searches":0}
        for day in (start+timedelta(days=i) for i in range(days))}
    for row in series:
        record=trends.get(row["day"])
        if record:record["views" if row["kind"]=="page_view" else "searches"]=int(row["n"])
    pages=db.all(
        "SELECT bucket AS path,SUM(n) AS views FROM atlas_analytics_daily "
        "WHERE day>=? AND kind='page_view' GROUP BY bucket ORDER BY views DESC LIMIT 20",
        (cutoff,)
    )
    terms=db.all(
        "SELECT bucket AS term,SUM(n) AS searches FROM atlas_analytics_daily "
        "WHERE day>=? AND kind='search' GROUP BY bucket ORDER BY searches DESC LIMIT 12",
        (cutoff,)
    )
    saved=Counter()
    for table in ("atlas_user_items","atlas_user_entities"):
        for row in db.all(
            "SELECT kind,slug,COUNT(*) AS n FROM "+table+
            " WHERE collection='saved' GROUP BY kind,slug"
        ):
            saved[(row["kind"],row["slug"])]+=int(row["n"])
    users=db.one("SELECT COUNT(*) AS n FROM atlas_users")
    registered=db.one("SELECT COUNT(*) AS n FROM atlas_users WHERE created_at>=?",(cutoff,))
    cat=seo_routes.catalog()
    known={"site":cat["sites"],"module":cat["modules"],
           "pattern":cat["patterns"],"article":cat["articles"]}
    def name_of(kind,slug):
        item=known.get(kind,{}).get(slug,{})
        return str(item.get("name") or item.get("title") or slug)[:110]
    top_pages=[]
    for row in pages:
        path=row["path"]
        parts=path.strip("/").split("/") if path!="/" else []
        kind={"websites":"site","sections":"module","patterns":"pattern","insights":"article"}.get(parts[0] if parts else "")
        label=name_of(kind,parts[1]) if len(parts)==2 and kind else {
          "/":"首页","/websites":"网站案例","/sections":"页面模块",
          "/patterns":"设计模式","/insights":"资讯文章"
        }.get(path,path)
        top_pages.append({"path":path,"label":label,"views":int(row["views"])})
    top_saved=[
        {"key":kind+":"+slug,"label":name_of(kind,slug),
         "url":"/"+{"site":"websites","module":"sections","pattern":"patterns","article":"insights"}[kind]+"/"+slug,
         "count":n}
        for (kind,slug),n in saved.most_common(12)
        if kind in known
    ]
    daily=list(trends.values())
    return {
        "period_days":days,"since":cutoff,"through":now.isoformat(),
        "collected_since":"部署本版本后开始收集；历史未采集访问不进行回填",
        "totals":{
            "page_views":sum(row["views"] for row in daily),
            "searches":sum(row["searches"] for row in daily),
            "active_saves":sum(saved.values()),
            "registered_users":int(users["n"]) if users else 0,
            "new_users":int(registered["n"]) if registered else 0
        },
        "daily":daily,"top_pages":top_pages[:12],"top_searches":terms,
        "top_saved":top_saved
    }

def register_analytics_routes(app:FastAPI):
    @app.post("/api/analytics/event",status_code=204,include_in_schema=False)
    def collect_event(data:PublicEvent,request:Request):
        origin=request.headers.get("origin","")
        if origin:
            parsed=urlsplit(origin)
            host=request.headers.get("host","").lower()
            if parsed.netloc.lower()!=host or parsed.scheme not in ("https","http"):
                user_auth.error(403,"请求来源不合法。")
        if not permitted(request):
            return Response(status_code=204)
        path=normalize_path(data.path)
        if path is None:return Response(status_code=204)
        if data.type=="search":
            if path not in ("/websites","/sections","/insights"):
                return Response(status_code=204)
            bucket=normalize_search(data.query)
        else:bucket=path
        if not bucket:return Response(status_code=204)
        try:
            ensure_analytics()
            with user_auth.db() as db:
                db.execute(
                    "INSERT INTO atlas_analytics_daily(day,kind,bucket,n) VALUES(?,?,?,1) "
                    "ON CONFLICT(day,kind,bucket) DO UPDATE SET n=atlas_analytics_daily.n+1",
                    (datetime.now(timezone.utc).date().isoformat(),data.type,bucket)
                )
        except Exception:
            # Anonymous measurement is optional and must never break navigation.
            return Response(status_code=204)
        return Response(status_code=204)

    @app.get("/api/admin/analytics",include_in_schema=False)
    def admin_report(request:Request,response:Response,days:int=30):
        if days not in (7,30,90):user_auth.error(422,"只能查询 7、30 或 90 天数据。")
        session=user_auth.required(request)
        if not admin_routes.admin_allowed(session):
            user_auth.error(403,"此账号没有查看运营数据的权限。")
        response.headers["Cache-Control"]="no-store"
        ensure_analytics()
        with user_auth.db() as db:return query_report(int(days),db)
