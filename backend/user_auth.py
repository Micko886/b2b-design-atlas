"""User accounts and private collections for B2B Atlas."""
from __future__ import annotations
import os, re, sqlite3, secrets, hashlib, hmac, threading, uuid
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from urllib.parse import urlparse
from typing import Literal
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

COOKIE="atlas_session"
TTL=30*24*3600
PG_URL=os.getenv("ATLAS_USERS_DATABASE_URL","").strip()
SQLITE_DEMO=os.getenv("ATLAS_ALLOW_EPHEMERAL_AUTH","0")=="1"
SQLITE_FILE=os.getenv("ATLAS_USERS_DB_PATH","/srv/atlas/data/users-demo.sqlite3")
EMAIL=re.compile(r"^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,40}$")
KEY=re.compile(r"^(site|module):([a-z0-9][a-z0-9-]{0,110})$")
LOCK=threading.Lock()
READY=False
def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def sha(value): return hashlib.sha256(value.encode()).hexdigest()
def error(status,message): raise HTTPException(status_code=status,detail=message)

@contextmanager
def db():
    if PG_URL:
        import psycopg
        from psycopg.rows import dict_row
        con=psycopg.connect(PG_URL,row_factory=dict_row,connect_timeout=8)
        pg=True
    elif SQLITE_DEMO:
        os.makedirs(os.path.dirname(SQLITE_FILE),exist_ok=True)
        con=sqlite3.connect(SQLITE_FILE,timeout=8)
        con.row_factory=sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        pg=False
    else:
        error(503,"账号数据库尚未配置。")
    class DB:
        def execute(self,sql,args=()): return con.execute(sql.replace("?","%s") if pg else sql,args)
        def one(self,sql,args=()):
            row=self.execute(sql,args).fetchone()
            return dict(row) if row else None
        def all(self,sql,args=()): return [dict(r) for r in self.execute(sql,args).fetchall()]
    try:
        yield DB()
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()

SCHEMA=[
"""CREATE TABLE IF NOT EXISTS atlas_users (
id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,display_name TEXT NOT NULL,
password_hash TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS atlas_sessions (
token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
csrf_token TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL)""",
"""CREATE INDEX IF NOT EXISTS atlas_sessions_user ON atlas_sessions(user_id)""",
"""CREATE TABLE IF NOT EXISTS atlas_user_items (
user_id TEXT NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
collection TEXT NOT NULL CHECK(collection IN ('saved','board')),
kind TEXT NOT NULL CHECK(kind IN ('site','module')),
slug TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,
PRIMARY KEY(user_id,collection,kind,slug))""",
"""CREATE INDEX IF NOT EXISTS atlas_items_user ON atlas_user_items(user_id,collection)""",
"""CREATE TABLE IF NOT EXISTS atlas_auth_limits (
fingerprint TEXT PRIMARY KEY,window_end TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0)"""
]
def ensure_ready():
    global READY
    if READY:return
    if not PG_URL and not SQLITE_DEMO:error(503,"账号服务尚未配置持久化数据库。")
    with LOCK:
        if READY:return
        try:
            with db() as conn:
                for sql in SCHEMA:conn.execute(sql)
            READY=True
        except HTTPException:raise
        except Exception:error(503,"账号数据库暂时不可用。")

def hash_password(value):
    salt=secrets.token_bytes(16)
    rounds=600000
    digest=hashlib.pbkdf2_hmac("sha256",value.encode(),salt,rounds)
    return "pbkdf2-sha256$"+str(rounds)+"$"+salt.hex()+"$"+digest.hex()
def check_password(value,encoded):
    try:
        method,rounds,salt,digest=encoded.split("$")
        if method!="pbkdf2-sha256":return False
        actual=hashlib.pbkdf2_hmac("sha256",value.encode(),bytes.fromhex(salt),int(rounds))
        return hmac.compare_digest(actual,bytes.fromhex(digest))
    except (ValueError,TypeError):return False
DUMMY=hash_password("a-dummy-password-for-login-timing")

def origin(request):
    site=request.headers.get("origin")
    if site:
        parsed=urlparse(site)
        if parsed.scheme!="https" or parsed.netloc.lower()!=request.headers.get("host","").lower():
            error(403,"请求来源不合法。")
def check_csrf(request,session):
    value=request.headers.get("x-csrf-token","")
    if not value or not hmac.compare_digest(value,session["csrf_token"]):
        error(403,"安全验证失败，请刷新页面后重试。")
def limit(request,action,max_attempts,seconds):
    ip=request.client.host if request.client else "unknown"
    fingerprint=sha(action+"|"+ip)
    end=(datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat(timespec="seconds")
    with db() as conn:
        row=conn.one("SELECT window_end,attempts FROM atlas_auth_limits WHERE fingerprint=?",(fingerprint,))
        if not row or row["window_end"]<now():
            conn.execute("""INSERT INTO atlas_auth_limits(fingerprint,window_end,attempts)
            VALUES(?,?,1) ON CONFLICT(fingerprint)
            DO UPDATE SET window_end=excluded.window_end,attempts=1""",(fingerprint,end))
        elif row["attempts"]>=max_attempts:error(429,"尝试次数过多，请稍后再试。")
        else:conn.execute("UPDATE atlas_auth_limits SET attempts=attempts+1 WHERE fingerprint=?",(fingerprint,))
def session(request):
    ensure_ready()
    token=request.cookies.get(COOKIE,"")
    if len(token)<32:return None
    with db() as conn:
        row=conn.one("""SELECT s.token_hash,s.user_id,s.csrf_token,s.expires_at,
        u.email,u.display_name,u.created_at AS user_created_at
        FROM atlas_sessions s JOIN atlas_users u ON u.id=s.user_id
        WHERE s.token_hash=?""",(sha(token),))
    return row if row and row["expires_at"]>now() else None
def required(request):
    s=session(request)
    if not s:error(401,"请先登录后使用个人收藏与研究板。")
    return s
def public_user(s):
    return {"id":s.get("user_id",s.get("id")),"email":s["email"],
            "display_name":s["display_name"],"created_at":s.get("user_created_at",s.get("created_at",""))}
def grant(conn,response,user_id):
    token=secrets.token_urlsafe(40)
    csrf=secrets.token_urlsafe(32)
    expiry=(datetime.now(timezone.utc)+timedelta(seconds=TTL)).isoformat(timespec="seconds")
    conn.execute("INSERT INTO atlas_sessions(token_hash,user_id,csrf_token,expires_at,created_at) VALUES(?,?,?,?,?)",
                 (sha(token),user_id,csrf,expiry,now()))
    response.set_cookie(COOKIE,token,max_age=TTL,path="/",secure=True,httponly=True,samesite="lax")
    response.headers["Cache-Control"]="no-store"
    return csrf

class Register(BaseModel):
    email:str=Field(min_length=5,max_length=254)
    display_name:str=Field(min_length=2,max_length=48)
    password:str=Field(min_length=10,max_length=128)
    @field_validator("email")
    @classmethod
    def clean_email(cls,v):
        v=v.strip().casefold()
        if not EMAIL.fullmatch(v):raise ValueError("邮箱格式不正确")
        return v
    @field_validator("display_name")
    @classmethod
    def clean_name(cls,v):
        v=v.strip()
        if not v or any(ord(c)<32 for c in v):raise ValueError("昵称格式不正确")
        return v
class Login(BaseModel):
    email:str=Field(min_length=5,max_length=254)
    password:str=Field(min_length=1,max_length=128)
class Item(BaseModel):
    collection:Literal["saved","board"]
    key:str=Field(max_length=125)
    @field_validator("key")
    @classmethod
    def clean_key(cls,v):
        if not KEY.fullmatch(v):raise ValueError("资源标识无效")
        return v
class Note(BaseModel):
    key:str=Field(max_length=125)
    note:str=Field(max_length=3000)
    @field_validator("key")
    @classmethod
    def clean_key(cls,v):
        if not KEY.fullmatch(v):raise ValueError("资源标识无效")
        return v
class Profile(BaseModel):
    display_name:str=Field(min_length=2,max_length=48)
    @field_validator("display_name")
    @classmethod
    def clean_name(cls,v):
        v=v.strip()
        if any(ord(c)<32 for c in v):raise ValueError("昵称格式不正确")
        return v
class ChangePassword(BaseModel):
    current_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=10,max_length=128)

def register_auth_routes(app:FastAPI):
    router=APIRouter(prefix="/api")
    @router.get("/auth/status")
    def status():
        if not PG_URL and not SQLITE_DEMO:
            return {"available":False,"mode":"unconfigured","message":"账号服务正在配置持久化数据库，暂时不可注册。"}
        try:
            ensure_ready()
            return {"available":True,"mode":"postgres" if PG_URL else "demo",
                    "message":"" if PG_URL else "演示存储：重新部署或服务重启后账号和收藏可能丢失。"}
        except HTTPException:
            return {"available":False,"mode":"unavailable","message":"账号数据库暂时不可用。"}
    @router.get("/auth/me")
    def me(request:Request,response:Response):
        response.headers["Cache-Control"]="no-store"
        s=session(request)
        return {"authenticated":True,"user":public_user(s),"csrf_token":s["csrf_token"]} if s else {"authenticated":False,"user":None}
    @router.post("/auth/register",status_code=201)
    def register(data:Register,request:Request,response:Response):
        origin(request);ensure_ready();limit(request,"register",6,3600)
        with db() as conn:
            if conn.one("SELECT id FROM atlas_users WHERE email=?",(data.email,)):error(409,"此邮箱已注册。")
            uid=str(uuid.uuid4())
            try:
                conn.execute("INSERT INTO atlas_users(id,email,display_name,password_hash,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                             (uid,data.email,data.display_name,hash_password(data.password),now(),now()))
            except Exception:error(409,"此邮箱已注册。")
            csrf=grant(conn,response,uid)
        return {"authenticated":True,"user":{"id":uid,"email":data.email,"display_name":data.display_name,"created_at":now()},"csrf_token":csrf}
    @router.post("/auth/login")
    def login(data:Login,request:Request,response:Response):
        origin(request);ensure_ready();limit(request,"login",15,900)
        with db() as conn:
            row=conn.one("SELECT id,email,display_name,password_hash,created_at FROM atlas_users WHERE email=?",(data.email.strip().casefold(),))
            ok=check_password(data.password,row["password_hash"] if row else DUMMY)
            if not row or not ok:error(401,"邮箱或密码不正确。")
            csrf=grant(conn,response,row["id"])
        return {"authenticated":True,"user":public_user(row),"csrf_token":csrf}
    @router.post("/auth/logout")
    def logout(request:Request,response:Response):
        origin(request);s=required(request);check_csrf(request,s)
        with db() as conn:conn.execute("DELETE FROM atlas_sessions WHERE token_hash=?",(s["token_hash"],))
        response.delete_cookie(COOKIE,path="/",secure=True,httponly=True,samesite="lax")
        response.headers["Cache-Control"]="no-store"
        return {"ok":True}
    @router.patch("/auth/profile")
    def profile(data:Profile,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        with db() as conn:
            conn.execute("UPDATE atlas_users SET display_name=?,updated_at=? WHERE id=?",(data.display_name,now(),s["user_id"]))
        return {"ok":True,"user":{"id":s["user_id"],"email":s["email"],"display_name":data.display_name,"created_at":s["user_created_at"]}}
    @router.post("/auth/change-password")
    def change_password(data:ChangePassword,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        with db() as conn:
            user=conn.one("SELECT password_hash FROM atlas_users WHERE id=?",(s["user_id"],))
            if not user or not check_password(data.current_password,user["password_hash"]):error(400,"原密码不正确。")
            conn.execute("UPDATE atlas_users SET password_hash=?,updated_at=? WHERE id=?",(hash_password(data.new_password),now(),s["user_id"]))
            conn.execute("DELETE FROM atlas_sessions WHERE user_id=? AND token_hash<>?",(s["user_id"],s["token_hash"]))
        return {"ok":True}
    @router.get("/me/library")
    def library(request:Request,response:Response):
        s=required(request);response.headers["Cache-Control"]="no-store"
        with db() as conn:
            items=conn.all("SELECT collection,kind,slug,note FROM atlas_user_items WHERE user_id=? ORDER BY created_at DESC",(s["user_id"],))
        return {"saved":[x["kind"]+":"+x["slug"] for x in items if x["collection"]=="saved"],
                "board":[x["kind"]+":"+x["slug"] for x in items if x["collection"]=="board"],
                "notes":{x["kind"]+":"+x["slug"]:x["note"] for x in items if x["collection"]=="board" and x["note"]}}
    @router.post("/me/library",status_code=201)
    def add(data:Item,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        kind,slug=KEY.fullmatch(data.key).groups()
        with db() as conn:
            conn.execute("""INSERT INTO atlas_user_items(user_id,collection,kind,slug,note,created_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,collection,kind,slug) DO NOTHING""",
            (s["user_id"],data.collection,kind,slug,"",now()))
        return {"ok":True}
    @router.delete("/me/library/{collection}/{kind}/{slug}")
    def remove(collection:Literal["saved","board"],kind:Literal["site","module"],slug:str,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,110}",slug):error(400,"资源标识无效。")
        with db() as conn:
            conn.execute("DELETE FROM atlas_user_items WHERE user_id=? AND collection=? AND kind=? AND slug=?",
                         (s["user_id"],collection,kind,slug))
        return {"ok":True}
    @router.patch("/me/library/note")
    def note(data:Note,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        kind,slug=KEY.fullmatch(data.key).groups()
        with db() as conn:
            conn.execute("""UPDATE atlas_user_items SET note=?
            WHERE user_id=? AND collection='board' AND kind=? AND slug=?""",(data.note,s["user_id"],kind,slug))
        return {"ok":True}
    app.include_router(router)
