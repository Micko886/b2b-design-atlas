"""V51.8–V51.12 · First-party privacy-conscious acquisition and engagement analytics.

A random tab-session ID is hashed before persistence. No IP, user ID, cookie,
full referrer URL, precise location or raw browser UA is retained. Anonymous
events never grant permission; registration / saved conversions are credited
only after successful authenticated server actions.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, Field

from app import admin_routes, user_auth, seo_routes
from app.analytics_routes import normalize_path, permitted

SESSION_PATTERN=re.compile(r"^[a-f0-9-]{36}$")
TOKEN_PATTERN=re.compile(r"^[a-z0-9][a-z0-9_.-]{0,47}$")
HOST_PATTERN=re.compile(r"^[a-z0-9][a-z0-9.-]{0,120}[a-z0-9]$")
BOT_PATTERN=re.compile(r"bot|spider|crawler|headless|wget|curl|python-requests",re.I)
KINDS={"websites":"site","sections":"module","patterns":"pattern","insights":"article"}
CHANNELS=("direct","organic","social","referral","paid","email")
SCHEMA=[
    """CREATE TABLE IF NOT EXISTS atlas_growth_sessions(
        sid TEXT PRIMARY KEY,started_at TEXT NOT NULL,last_seen TEXT NOT NULL,
        channel TEXT NOT NULL,source TEXT NOT NULL,medium TEXT NOT NULL,
        campaign TEXT NOT NULL,referrer TEXT NOT NULL,
        landing TEXT NOT NULL,device TEXT NOT NULL,
        registered INTEGER NOT NULL DEFAULT 0,saved INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE INDEX IF NOT EXISTS atlas_growth_session_time ON atlas_growth_sessions(started_at)""",
    """CREATE TABLE IF NOT EXISTS atlas_growth_daily(
        day TEXT NOT NULL,sid TEXT NOT NULL,
        channel TEXT NOT NULL,source TEXT NOT NULL,medium TEXT NOT NULL,
        campaign TEXT NOT NULL,referrer TEXT NOT NULL,
        landing TEXT NOT NULL,device TEXT NOT NULL,
        views INTEGER NOT NULL DEFAULT 0,searches INTEGER NOT NULL DEFAULT 0,
        previews INTEGER NOT NULL DEFAULT 0,external_clicks INTEGER NOT NULL DEFAULT 0,
        content_clicks INTEGER NOT NULL DEFAULT 0,
        scroll_depth INTEGER NOT NULL DEFAULT 0,
        registrations INTEGER NOT NULL DEFAULT 0,
        first_saves INTEGER NOT NULL DEFAULT 0,
        signup_to_save INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(day,sid)
    )""",
    """CREATE INDEX IF NOT EXISTS atlas_growth_daily_time ON atlas_growth_daily(day)""",
    """CREATE INDEX IF NOT EXISTS atlas_growth_daily_channel ON atlas_growth_daily(day,channel)""",
    """CREATE TABLE IF NOT EXISTS atlas_growth_content(
        day TEXT NOT NULL,path TEXT NOT NULL,
        views INTEGER NOT NULL DEFAULT 0,
        previews INTEGER NOT NULL DEFAULT 0,
        content_clicks INTEGER NOT NULL DEFAULT 0,
        external_clicks INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(day,path)
    )""",
    """CREATE INDEX IF NOT EXISTS atlas_growth_content_day ON atlas_growth_content(day)"""
]
SCHEMA_LOCK=threading.Lock()
SCHEMA_READY=False
LAST_PRUNE=0.0

class GrowthEvent(BaseModel):
    event: Literal["page_view","search","preview","external_click","content_click","scroll"]
    session: str=Field(min_length=36,max_length=36)
    path: str=Field(default="/",max_length=180)
    target: str=Field(default="",max_length=180)
    referrer: str=Field(default="",max_length=220)
    utm_source: str=Field(default="",max_length=80)
    utm_medium: str=Field(default="",max_length=80)
    utm_campaign: str=Field(default="",max_length=80)
    device: Literal["desktop","tablet","mobile","unknown"]="unknown"
    depth: int=Field(default=0,ge=0,le=100)

def token(value):
    item=str(value or "").strip().lower()
    if "@" in item or re.search(r"\d{7,}",item):return ""
    return item if TOKEN_PATTERN.fullmatch(item) else ""

def referrer_host(value,site_host=""):
    if not value:return ""
    try:
        uri=urlsplit(value)
        host=(uri.hostname or "").lower().removeprefix("www.")
        if uri.scheme not in ("http","https") or not HOST_PATTERN.fullmatch(host):
            return ""
        if host==site_host.lower().removeprefix("www.") or "." not in host:
            return ""
        ipaddress.ip_address(host)
        return ""
    except ValueError:
        return host
    except Exception:
        return ""

def classify_source(data,site_host=""):
    source=token(data.utm_source)
    medium=token(data.utm_medium)
    campaign=token(data.utm_campaign)
    host=referrer_host(data.referrer,site_host)
    if medium in ("cpc","ppc","paid","paid-social","display","ads"):
        channel="paid"
    elif medium in ("email","newsletter"):
        channel="email"
    elif medium in ("social","social-media","organic-social"):
        channel="social"
    elif medium in ("organic","search","seo"):
        channel="organic"
    elif source in ("google","bing","duckduckgo","baidu","yandex","yahoo"):
        channel="organic"
    elif source in ("linkedin","facebook","instagram","twitter","x","reddit","pinterest","tiktok"):
        channel="social"
    elif source in ("newsletter","mailchimp","substack","email"):
        channel="email"
    elif source and medium:
        channel="referral"
    elif host:
        if any(x in host for x in ("google.","bing.","duckduckgo.","yahoo.","baidu.","yandex.")):
            channel="organic"
        elif any(x in host for x in ("linkedin.","facebook.","instagram.","x.com","twitter.","reddit.","pinterest.","tiktok.")):
            channel="social"
        else:channel="referral"
    else:channel="direct"
    return {"channel":channel,"source":source or host or "direct",
            "medium":medium,"campaign":campaign,"referrer":host}

def ensure_growth():
    global SCHEMA_READY
    if SCHEMA_READY:return
    user_auth.ensure_ready()
    with SCHEMA_LOCK:
        if SCHEMA_READY:return
        with user_auth.db() as db:
            for sql in SCHEMA:db.execute(sql)
        SCHEMA_READY=True

def hash_sid(sid):
    if not isinstance(sid,str) or not SESSION_PATTERN.fullmatch(sid):return None
    return hashlib.sha256(sid.encode("ascii")).hexdigest()

def prune(db):
    global LAST_PRUNE
    current=time.monotonic()
    if current-LAST_PRUNE < 3600:return
    LAST_PRUNE=current
    before=(datetime.now(timezone.utc)-timedelta(days=95)).isoformat()
    cutoff=(datetime.now(timezone.utc)-timedelta(days=95)).date().isoformat()
    db.execute("DELETE FROM atlas_growth_sessions WHERE last_seen<?",(before,))
    db.execute("DELETE FROM atlas_growth_daily WHERE day<?",(cutoff,))
    db.execute("DELETE FROM atlas_growth_content WHERE day<?",(cutoff,))

def touch_day(db,sid,day,session):
    db.execute("""INSERT INTO atlas_growth_daily
        (day,sid,channel,source,medium,campaign,referrer,landing,device)
        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(day,sid) DO NOTHING""",
        (day,sid,session["channel"],session["source"],session["medium"],
         session["campaign"],session["referrer"],session["landing"],session["device"]))

def content_inc(db,day,path,column):
    # Column names are selected by code constants, never from user input.
    if column not in ("views","previews","external_clicks","content_clicks"):return
    db.execute("INSERT INTO atlas_growth_content(day,path) VALUES(?,?) ON CONFLICT(day,path) DO NOTHING",
               (day,path))
    db.execute("UPDATE atlas_growth_content SET "+column+"="+column+"+1 WHERE day=? AND path=?",
               (day,path))

def ingest(db,data,site_host="",now=None):
    now=now or datetime.now(timezone.utc)
    sid=hash_sid(data.session)
    path=normalize_path(data.path)
    if not sid or not path:return False
    target=normalize_path(data.target) if data.target else None
    if data.event=="content_click" and (not target or len(target.strip("/").split("/"))!=2):
        return False
    if data.event=="scroll" and data.depth not in (25,50,75,90):
        return False
    session=db.one("SELECT * FROM atlas_growth_sessions WHERE sid=?",(sid,))
    iso=now.isoformat(timespec="seconds")
    day=now.date().isoformat()
    if session:
        last=datetime.fromisoformat(session["last_seen"])
        if last.tzinfo is None:last=last.replace(tzinfo=timezone.utc)
        if now-last>timedelta(minutes=45):return False
    else:
        # Anonymous acquisition is defined by the first actual page view.
        if data.event!="page_view":return False
        meta=classify_source(data,site_host)
        db.execute("""INSERT INTO atlas_growth_sessions
           (sid,started_at,last_seen,channel,source,medium,campaign,referrer,landing,device)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
           (sid,iso,iso,meta["channel"],meta["source"],meta["medium"],meta["campaign"],
            meta["referrer"],path,data.device))
        session=db.one("SELECT * FROM atlas_growth_sessions WHERE sid=?",(sid,))
    db.execute("UPDATE atlas_growth_sessions SET last_seen=? WHERE sid=?",(iso,sid))
    touch_day(db,sid,day,session)
    columns={"page_view":"views","search":"searches","preview":"previews",
             "external_click":"external_clicks","content_click":"content_clicks"}
    if data.event=="scroll":
        db.execute("""UPDATE atlas_growth_daily SET
            scroll_depth=CASE WHEN scroll_depth<? THEN ? ELSE scroll_depth END
            WHERE day=? AND sid=?""",(data.depth,data.depth,day,sid))
    else:
        column=columns[data.event]
        db.execute("UPDATE atlas_growth_daily SET "+column+"="+column+"+1 WHERE day=? AND sid=?",(day,sid))
        if data.event in ("page_view","preview","external_click","content_click"):
            content_inc(db,day,target if data.event=="content_click" else path,column)
    prune(db)
    return True

def record_conversion(raw_sid,kind):
    """Called by successful server-side signup and first-save operations.

    No user/account identifier is stored; credit is limited to a live anonymous
    session. Failures cannot prevent the real user action from succeeding.
    """
    sid=hash_sid(raw_sid)
    if not sid or kind not in ("registration","save"):return False
    try:
        ensure_growth()
        with user_auth.db() as db:
            row=db.one("SELECT * FROM atlas_growth_sessions WHERE sid=?",(sid,))
            if not row:return False
            now=datetime.now(timezone.utc)
            last=datetime.fromisoformat(row["last_seen"])
            if last.tzinfo is None:last=last.replace(tzinfo=timezone.utc)
            if now-last>timedelta(minutes=45):return False
            field="registered" if kind=="registration" else "saved"
            if row[field]:return False
            result=db.execute("UPDATE atlas_growth_sessions SET "+field+"=1 WHERE sid=? AND "+field+"=0",(sid,))
            if result.rowcount!=1:return False
            day=now.date().isoformat()
            touch_day(db,sid,day,row)
            column="registrations" if kind=="registration" else "first_saves"
            db.execute("UPDATE atlas_growth_daily SET "+column+"="+column+"+1 WHERE day=? AND sid=?",(day,sid))
            if kind=="save" and row["registered"]:
                db.execute("UPDATE atlas_growth_daily SET signup_to_save=signup_to_save+1 WHERE day=? AND sid=?",(day,sid))
        return True
    except Exception:return False

def report(days,db,channel="all",now=None):
    now=now or datetime.now(timezone.utc)
    end=now.date()
    start=end-timedelta(days=days-1)
    cutoff=start.isoformat()
    if channel not in CHANNELS:channel="all"
    args=(cutoff,) if channel=="all" else (cutoff,channel)
    where="day>=?" + ("" if channel=="all" else " AND channel=?")
    rows=db.all("SELECT * FROM atlas_growth_daily WHERE "+where,args)
    # Each DB row is a session-day, never an individual user's identity.
    sessions={r["sid"] for r in rows}
    daily={ (start+timedelta(days=i)).isoformat():
        {"date":(start+timedelta(days=i)).isoformat(),"sessions":0,
         "views":0,"searches":0,"external_clicks":0,"registrations":0,"first_saves":0}
        for i in range(days)}
    counts={}
    def grouping(field,raw):
        key=raw[field] or ("direct" if field=="channel" else "unknown")
        row=counts.setdefault((field,key),{"key":key,"sessions":set(),"views":0,
            "searches":0,"external_clicks":0,"registrations":0,"first_saves":0})
        row["sessions"].add(raw["sid"])
        for metric in ("views","searches","external_clicks","registrations","first_saves"):
            row[metric]+=int(raw[metric])
    total_metrics=("views","searches","previews","external_clicks","content_clicks",
                   "registrations","first_saves","signup_to_save")
    total={key:sum(int(r[key]) for r in rows) for key in total_metrics}
    engaged=set();depths={25:0,50:0,75:0,90:0}
    scroll_max={}
    for row in rows:
        item=daily[row["day"]]
        item["sessions"]+=1  # active session-days; distinct for every calendar day
        for metric in ("views","searches","external_clicks","registrations","first_saves"):
            item[metric]+=int(row[metric])
        if int(row["views"])>=2 or int(row["scroll_depth"])>=50 or int(row["searches"])+int(row["previews"])+int(row["external_clicks"])+int(row["content_clicks"])>0:
            engaged.add(row["sid"])
        scroll_max[row["sid"]]=max(scroll_max.get(row["sid"],0),int(row["scroll_depth"]))
        for field in ("channel","source","medium","campaign","referrer","landing","device"):
            grouping(field,row)
    for max_depth in scroll_max.values():
        for d in depths:
            if max_depth>=d:depths[d]+=1
    def aggregates(field,limit=12):
        items=[{"key":v["key"],"sessions":len(v["sessions"]),"views":v["views"],
                "searches":v["searches"],"external_clicks":v["external_clicks"],
                "registrations":v["registrations"],"first_saves":v["first_saves"]}
               for (f,_),v in counts.items() if f==field]
        return sorted(items,key=lambda v:(-v["sessions"],v["key"]))[:limit]
    summary={"sessions":len(sessions),"engaged_sessions":len(engaged),**total}
    summary["engagement_rate"]=round(len(engaged)*100/len(sessions),1) if sessions else 0
    for action in ("registrations","first_saves","signup_to_save"):
        summary[action+"_rate"]=round(100*summary[action]/len(sessions),1) if sessions else 0
    content=db.all("""SELECT path,SUM(views) AS views,
        SUM(previews) AS previews,SUM(external_clicks) AS external_clicks,
        SUM(content_clicks) AS content_clicks
        FROM atlas_growth_content WHERE day>=?
        GROUP BY path ORDER BY views DESC,external_clicks DESC LIMIT 100""",(cutoff,))
    valid_content=[]
    for item in content:
        if not normalize_path(item["path"]):continue
        if len(item["path"].strip("/").split("/"))!=2:continue
        valid_content.append({**item,
            "views":int(item["views"]),"previews":int(item["previews"]),
            "external_clicks":int(item["external_clicks"]),
            "content_clicks":int(item["content_clicks"])})
    return {"days":days,"since":cutoff,"through":end.isoformat(),"channel_filter":channel,
            "tracking_since":"V51.8 上线后开始采集；匿名会话按标签页和 30 分钟活动窗口估算，非跨设备独立访客",
            "totals":summary,"daily":list(daily.values()),"channels":aggregates("channel",10),
            "sources":aggregates("source",12),"mediums":aggregates("medium",12),
            "campaigns":[r for r in aggregates("campaign",20) if r["key"]!="unknown"],
            "referrers":[r for r in aggregates("referrer",20) if r["key"]!="unknown"],
            "devices":aggregates("device",5),"landing_pages":aggregates("landing",12),
            "scroll_depth":[{"depth":d,"sessions":n} for d,n in depths.items()],
            "content":valid_content[:20],
            "note":"注册和首次收藏仅统计可归因至有效匿名会话的服务端成功操作；无法归因的操作不分配渠道。"}

def register_growth_routes(app:FastAPI):
    @app.post("/api/analytics/growth",include_in_schema=False,status_code=204)
    def collect(data:GrowthEvent,request:Request):
        origin=request.headers.get("origin","")
        if origin:
            parsed=urlsplit(origin)
            if parsed.netloc.lower()!=request.headers.get("host","").lower() or parsed.scheme not in ("https","http"):
                user_auth.error(403,"请求来源不合法。")
        if BOT_PATTERN.search(request.headers.get("user-agent","")):
            return Response(status_code=204)
        if not permitted(request):return Response(status_code=204)
        try:
            ensure_growth()
            with user_auth.db() as db:
                ingest(db,data,request.headers.get("host","").split(":")[0])
        except Exception:
            # Analytics must not interrupt browsing even when temporarily offline.
            pass
        return Response(status_code=204)

    @app.get("/api/admin/growth",include_in_schema=False)
    def dashboard(request:Request,response:Response,days:Literal[7,30,90]=30,
                  channel:Literal["all","direct","organic","social","referral","paid","email"]="all"):
        session=user_auth.required(request)
        if not admin_routes.admin_allowed(session):
            user_auth.error(403,"需要管理员权限。")
        response.headers["Cache-Control"]="no-store"
        ensure_growth()
        with user_auth.db() as db:return report(int(days),db,channel)
