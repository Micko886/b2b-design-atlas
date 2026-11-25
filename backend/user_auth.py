"""User accounts and private collections for B2B Atlas."""
from __future__ import annotations
import os, re, sqlite3, secrets, hashlib, hmac, threading, uuid, smtplib
from email.message import EmailMessage
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
SMTP_HOST=os.getenv("ATLAS_SMTP_HOST","").strip()
SMTP_USER=os.getenv("ATLAS_SMTP_USER","").strip()
SMTP_PASS=os.getenv("ATLAS_SMTP_PASSWORD","")
SMTP_FROM=os.getenv("ATLAS_SMTP_FROM","").strip()
SMTP_PORT=int(os.getenv("ATLAS_SMTP_PORT","587"))
RESET_EMAIL_ENABLED=bool(SMTP_HOST and SMTP_USER and SMTP_PASS and SMTP_FROM)
EMAIL=re.compile(r"^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,40}$")
KEY=re.compile(r"^(site|module|pattern|article):([a-z0-9][a-z0-9-]{0,110})$")
FOLDER_ID=re.compile(r"^[0-9a-f-]{36}$")
COLOR=re.compile(r"^#[0-9a-fA-F]{6}$")
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
fingerprint TEXT PRIMARY KEY,window_end TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0)""",
"""CREATE TABLE IF NOT EXISTS atlas_user_entities (
user_id TEXT NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
collection TEXT NOT NULL CHECK(collection IN ('saved','board')),
kind TEXT NOT NULL CHECK(kind IN ('pattern','article')),
slug TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,
PRIMARY KEY(user_id,collection,kind,slug))""",
"""CREATE TABLE IF NOT EXISTS atlas_user_folders (
id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
name TEXT NOT NULL,name_key TEXT NOT NULL,color TEXT NOT NULL DEFAULT '#315BE8',
created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(user_id,name_key))""",
"""CREATE INDEX IF NOT EXISTS atlas_folders_user ON atlas_user_folders(user_id)""",
"""CREATE TABLE IF NOT EXISTS atlas_user_folder_items (
folder_id TEXT NOT NULL REFERENCES atlas_user_folders(id) ON DELETE CASCADE,
kind TEXT NOT NULL CHECK(kind IN ('site','module','pattern','article')),
slug TEXT NOT NULL,created_at TEXT NOT NULL,
PRIMARY KEY(folder_id,kind,slug))""",
"""CREATE TABLE IF NOT EXISTS atlas_item_annotations (
user_id TEXT NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
kind TEXT NOT NULL CHECK(kind IN ('site','module','pattern','article')),
slug TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',tags_json TEXT NOT NULL DEFAULT '[]',
updated_at TEXT NOT NULL,PRIMARY KEY(user_id,kind,slug))""",
"""CREATE TABLE IF NOT EXISTS atlas_user_comparisons (
id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
name TEXT NOT NULL,site_ids_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""",
"""CREATE INDEX IF NOT EXISTS atlas_comparisons_user ON atlas_user_comparisons(user_id,created_at)""",
"""CREATE TABLE IF NOT EXISTS atlas_password_resets (
token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
expires_at TEXT NOT NULL,created_at TEXT NOT NULL)"""
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
                # One-time owner provisioning. Credentials come only from
                # private runtime environment variables, never source control.
                bootstrap_id=os.getenv("ATLAS_BOOTSTRAP_ADMIN_ID","").strip().lower()
                bootstrap_email=os.getenv("ATLAS_BOOTSTRAP_ADMIN_EMAIL","").strip().casefold()
                bootstrap_password=os.getenv("ATLAS_BOOTSTRAP_ADMIN_PASSWORD","")
                if bootstrap_id and bootstrap_email and bootstrap_password:
                    try:uuid.UUID(bootstrap_id)
                    except ValueError:raise RuntimeError("Invalid bootstrap administrator ID")
                    if not EMAIL.fullmatch(bootstrap_email) or len(bootstrap_password)<24:
                        raise RuntimeError("Invalid bootstrap administrator credentials")
                    row=conn.one("SELECT id FROM atlas_users WHERE id=? OR email=?",
                                 (bootstrap_id,bootstrap_email))
                    if row and row["id"]!=bootstrap_id:
                        raise RuntimeError("Bootstrap administrator address already belongs to another account")
                    if not row:
                        stamp=now()
                        conn.execute("INSERT INTO atlas_users(id,email,display_name,password_hash,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                                     (bootstrap_id,bootstrap_email,"Atlas 管理员",hash_password(bootstrap_password),stamp,stamp))
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

class ResetRequest(BaseModel):
    email:str=Field(min_length=5,max_length=254)
    @field_validator("email")
    @classmethod
    def clean_email(cls,v):
        v=v.strip().casefold()
        if not EMAIL.fullmatch(v):raise ValueError("邮箱格式不正确")
        return v
class ResetComplete(BaseModel):
    token:str=Field(min_length=40,max_length=160)
    new_password:str=Field(min_length=10,max_length=128)

def send_reset_email(to,token):
    msg=EmailMessage()
    msg["Subject"]="B2B Atlas · 重置账户密码"
    msg["From"]=SMTP_FROM
    msg["To"]=to
    url=os.getenv("ATLAS_PUBLIC_ORIGIN","https://b2b-design-atlas-preview.onrender.com").rstrip("/")+"/reset-password?token="+token
    msg.set_content("你正在重置 B2B Atlas 的登录密码。\n\n请在 20 分钟内打开以下链接：\n"+url+"\n\n如果不是你发起的操作，请忽略这封邮件。")
    with smtplib.SMTP(SMTP_HOST,SMTP_PORT,timeout=12) as server:
        server.starttls()
        server.login(SMTP_USER,SMTP_PASS)
        server.send_message(msg)

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

class FolderPayload(BaseModel):
    name:str=Field(min_length=1,max_length=50)
    color:str="#315BE8"
    @field_validator("name")
    @classmethod
    def clean_name(cls,v):
        v=v.strip()
        if not v or any(ord(x)<32 for x in v):raise ValueError("收藏夹名称无效。")
        return v
    @field_validator("color")
    @classmethod
    def clean_color(cls,v):
        if not COLOR.fullmatch(v):raise ValueError("收藏夹配色无效。")
        return v.upper()
class FolderItem(BaseModel):
    key:str=Field(max_length=125)
    @field_validator("key")
    @classmethod
    def valid_key(cls,v):
        if not KEY.fullmatch(v):raise ValueError("资源标识无效")
        return v
class Annotation(BaseModel):
    key:str=Field(max_length=125)
    note:str=Field(max_length=3000,default="")
    tags:list[str]=Field(default_factory=list,max_length=10)
    @field_validator("key")
    @classmethod
    def valid_key(cls,v):
        if not KEY.fullmatch(v):raise ValueError("资源标识无效")
        return v
    @field_validator("tags")
    @classmethod
    def valid_tags(cls,v):
        cleaned=[]
        for x in v:
            x=x.strip()
            if not x or len(x)>24 or any(ord(c)<32 for c in x):raise ValueError("标签格式不正确")
            if x.casefold() not in [a.casefold() for a in cleaned]:cleaned.append(x)
        return cleaned

class ComparisonPayload(BaseModel):
    name:str=Field(min_length=1,max_length=64)
    site_ids:list[str]=Field(min_length=2,max_length=4)
    @field_validator("name")
    @classmethod
    def clean_comparison_name(cls,v):
        v=v.strip()
        if not v or any(ord(c)<32 for c in v):raise ValueError("对比名称无效。")
        return v
    @field_validator("site_ids")
    @classmethod
    def clean_site_ids(cls,v):
        if not 2<=len(v)<=4:raise ValueError("一次对比需要选择 2–4 个网站。")
        if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,110}",x) for x in v):
            raise ValueError("网站标识无效。")
        if len(set(v))!=len(v):raise ValueError("同一网站不能重复加入对比。")
        return v


def register_auth_routes(app:FastAPI):
    router=APIRouter(prefix="/api")
    @router.get("/auth/status")
    def status():
        if not PG_URL and not SQLITE_DEMO:
            return {"available":False,"mode":"unconfigured","message":"账号服务正在配置持久化数据库，暂时不可注册。"}
        try:
            ensure_ready()
            return {"available":True,"mode":"postgres" if PG_URL else "demo",
                    "message":"" if PG_URL else "演示存储：重新部署或服务重启后账号和收藏可能丢失。","password_reset_available":RESET_EMAIL_ENABLED}
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
    def library_data(user_id):
        with db() as conn:
            items=conn.all("SELECT collection,kind,slug,note,created_at FROM atlas_user_items WHERE user_id=?",(user_id,))
            extra=conn.all("SELECT collection,kind,slug,note,created_at FROM atlas_user_entities WHERE user_id=?",(user_id,))
            folders=conn.all("""SELECT f.id,f.name,f.color,f.created_at,
                   (SELECT COUNT(*) FROM atlas_user_folder_items i WHERE i.folder_id=f.id) AS item_count
                   FROM atlas_user_folders f WHERE user_id=? ORDER BY f.created_at""",(user_id,))
            memberships=conn.all("""SELECT i.folder_id,i.kind,i.slug
                    FROM atlas_user_folder_items i
                    JOIN atlas_user_folders f ON f.id=i.folder_id WHERE f.user_id=?""",(user_id,))
            metadata=conn.all("SELECT kind,slug,note,tags_json FROM atlas_item_annotations WHERE user_id=?",(user_id,))
            comparisons=conn.all("SELECT id,name,site_ids_json,created_at,updated_at FROM atlas_user_comparisons WHERE user_id=? ORDER BY updated_at DESC",(user_id,))
        combined=sorted(items+extra,key=lambda x:x["created_at"],reverse=True)
        return {"saved":[x["kind"]+":"+x["slug"] for x in combined if x["collection"]=="saved"],
                "board":[x["kind"]+":"+x["slug"] for x in combined if x["collection"]=="board"],
                "notes":{x["kind"]+":"+x["slug"]:x["note"] for x in combined if x["collection"]=="board" and x["note"]},
                "folders":folders,"folderItems":{f["id"]:[x["kind"]+":"+x["slug"] for x in memberships if x["folder_id"]==f["id"]] for f in folders},
                "annotations":{x["kind"]+":"+x["slug"]:{"note":x["note"],"tags":__import__("json").loads(x["tags_json"])} for x in metadata},
                "comparisons":[{"id":x["id"],"name":x["name"],"site_ids":__import__("json").loads(x["site_ids_json"]),
                                "created_at":x["created_at"],"updated_at":x["updated_at"]} for x in comparisons]}
    def saved_in_db(conn,user_id,kind,slug):
        table="atlas_user_items" if kind in ("site","module") else "atlas_user_entities"
        return conn.one("SELECT slug FROM "+table+" WHERE user_id=? AND collection='saved' AND kind=? AND slug=?",(user_id,kind,slug)) is not None
    def folder_for_user(conn,user_id,folder_id):
        if not FOLDER_ID.fullmatch(folder_id):error(404,"收藏夹不存在。")
        folder=conn.one("SELECT id,name FROM atlas_user_folders WHERE id=? AND user_id=?",(folder_id,user_id))
        if not folder:error(404,"收藏夹不存在。")
        return folder
    @router.get("/me/library")
    def library(request:Request,response:Response):
        s=required(request);response.headers["Cache-Control"]="no-store"
        return library_data(s["user_id"])
    @router.post("/me/library",status_code=201)
    def add(data:Item,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        kind,slug=KEY.fullmatch(data.key).groups()
        table="atlas_user_items" if kind in ("site","module") else "atlas_user_entities"
        with db() as conn:
            conn.execute("""INSERT INTO """+table+"""(user_id,collection,kind,slug,note,created_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,collection,kind,slug) DO NOTHING""",
            (s["user_id"],data.collection,kind,slug,"",now()))
        return {"ok":True}
    @router.delete("/me/library/{collection}/{kind}/{slug}")
    def remove(collection:Literal["saved","board"],kind:Literal["site","module","pattern","article"],slug:str,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,110}",slug):error(400,"资源标识无效。")
        table="atlas_user_items" if kind in ("site","module") else "atlas_user_entities"
        with db() as conn:
            conn.execute("DELETE FROM "+table+" WHERE user_id=? AND collection=? AND kind=? AND slug=?",
                         (s["user_id"],collection,kind,slug))
            if collection=="saved":
                conn.execute("""DELETE FROM atlas_user_folder_items WHERE kind=? AND slug=? AND
                folder_id IN (SELECT id FROM atlas_user_folders WHERE user_id=?)""",(kind,slug,s["user_id"]))
                conn.execute("DELETE FROM atlas_item_annotations WHERE user_id=? AND kind=? AND slug=?",(s["user_id"],kind,slug))
        return {"ok":True}
    @router.patch("/me/library/note")
    def note(data:Note,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        kind,slug=KEY.fullmatch(data.key).groups()
        table="atlas_user_items" if kind in ("site","module") else "atlas_user_entities"
        with db() as conn:
            conn.execute("UPDATE "+table+" SET note=? WHERE user_id=? AND collection='board' AND kind=? AND slug=?",
                         (data.note,s["user_id"],kind,slug))
        return {"ok":True}

    @router.post("/me/folders",status_code=201)
    def folder_create(data:FolderPayload,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        uid=s["user_id"]
        with db() as conn:
            row=conn.one("SELECT COUNT(*) AS n FROM atlas_user_folders WHERE user_id=?",(uid,))
            if row["n"]>=40:error(409,"每个账户最多创建 40 个收藏夹。")
            if conn.one("SELECT id FROM atlas_user_folders WHERE user_id=? AND name_key=?",(uid,data.name.casefold())):
                error(409,"已存在同名收藏夹。")
            fid=str(uuid.uuid4())
            conn.execute("""INSERT INTO atlas_user_folders(id,user_id,name,name_key,color,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)""",(fid,uid,data.name,data.name.casefold(),data.color,now(),now()))
        return {"id":fid,"name":data.name,"color":data.color,"item_count":0}
    @router.patch("/me/folders/{folder_id}")
    def folder_update(folder_id:str,data:FolderPayload,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        with db() as conn:
            folder_for_user(conn,s["user_id"],folder_id)
            dup=conn.one("SELECT id FROM atlas_user_folders WHERE user_id=? AND name_key=?",
                         (s["user_id"],data.name.casefold()))
            if dup and dup["id"]!=folder_id:error(409,"已存在同名收藏夹。")
            conn.execute("UPDATE atlas_user_folders SET name=?,name_key=?,color=?,updated_at=? WHERE id=? AND user_id=?",
                         (data.name,data.name.casefold(),data.color,now(),folder_id,s["user_id"]))
        return {"ok":True}
    @router.delete("/me/folders/{folder_id}")
    def folder_delete(folder_id:str,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        with db() as conn:
            folder_for_user(conn,s["user_id"],folder_id)
            conn.execute("DELETE FROM atlas_user_folders WHERE id=? AND user_id=?",(folder_id,s["user_id"]))
        return {"ok":True}
    @router.post("/me/folders/{folder_id}/items",status_code=201)
    def folder_add_item(folder_id:str,data:FolderItem,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        kind,slug=KEY.fullmatch(data.key).groups()
        with db() as conn:
            folder_for_user(conn,s["user_id"],folder_id)
            if not saved_in_db(conn,s["user_id"],kind,slug):
                error(409,"请先收藏该资源，再加入收藏夹。")
            conn.execute("""INSERT INTO atlas_user_folder_items(folder_id,kind,slug,created_at)
              VALUES(?,?,?,?) ON CONFLICT(folder_id,kind,slug) DO NOTHING""",(folder_id,kind,slug,now()))
        return {"ok":True}
    @router.delete("/me/folders/{folder_id}/items/{kind}/{slug}")
    def folder_remove_item(folder_id:str,kind:Literal["site","module","pattern","article"],slug:str,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,110}",slug):error(400,"无效资源")
        with db() as conn:
            folder_for_user(conn,s["user_id"],folder_id)
            conn.execute("DELETE FROM atlas_user_folder_items WHERE folder_id=? AND kind=? AND slug=?",(folder_id,kind,slug))
        return {"ok":True}
    @router.patch("/me/library/annotation")
    def annotation_update(data:Annotation,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        kind,slug=KEY.fullmatch(data.key).groups()
        with db() as conn:
            if not saved_in_db(conn,s["user_id"],kind,slug):error(409,"请先收藏该资源。")
            conn.execute("""INSERT INTO atlas_item_annotations(user_id,kind,slug,note,tags_json,updated_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,kind,slug)
                DO UPDATE SET note=excluded.note,tags_json=excluded.tags_json,updated_at=excluded.updated_at""",
                (s["user_id"],kind,slug,data.note,__import__("json").dumps(data.tags,ensure_ascii=False),now()))
        return {"ok":True}
    @router.get("/me/comparisons")
    def list_comparisons(request:Request,response:Response):
        s=required(request);response.headers["Cache-Control"]="no-store"
        return library_data(s["user_id"])["comparisons"]
    @router.post("/me/comparisons",status_code=201)
    def create_comparison(data:ComparisonPayload,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        limit(request,"comparison-create",30,3600)
        uid=s["user_id"]
        with db() as conn:
            row=conn.one("SELECT COUNT(*) AS n FROM atlas_user_comparisons WHERE user_id=?",(uid,))
            if row["n"]>=40:error(409,"每个账户最多保存 40 组网站对比。")
            cid=str(uuid.uuid4());stamp=now()
            conn.execute("""INSERT INTO atlas_user_comparisons(id,user_id,name,site_ids_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?)""",(cid,uid,data.name,__import__("json").dumps(data.site_ids),stamp,stamp))
        return {"id":cid,"name":data.name,"site_ids":data.site_ids,"created_at":stamp,"updated_at":stamp}
    @router.patch("/me/comparisons/{comparison_id}")
    def update_comparison(comparison_id:str,data:ComparisonPayload,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        if not FOLDER_ID.fullmatch(comparison_id):error(404,"对比记录不存在。")
        with db() as conn:
            old=conn.one("SELECT id FROM atlas_user_comparisons WHERE id=? AND user_id=?",(comparison_id,s["user_id"]))
            if not old:error(404,"对比记录不存在。")
            stamp=now()
            conn.execute("UPDATE atlas_user_comparisons SET name=?,site_ids_json=?,updated_at=? WHERE id=? AND user_id=?",
                         (data.name,__import__("json").dumps(data.site_ids),stamp,comparison_id,s["user_id"]))
        return {"id":comparison_id,"name":data.name,"site_ids":data.site_ids,"updated_at":stamp}
    @router.delete("/me/comparisons/{comparison_id}")
    def delete_comparison(comparison_id:str,request:Request):
        origin(request);s=required(request);check_csrf(request,s)
        if not FOLDER_ID.fullmatch(comparison_id):error(404,"对比记录不存在。")
        with db() as conn:
            cur=conn.execute("DELETE FROM atlas_user_comparisons WHERE id=? AND user_id=?",(comparison_id,s["user_id"]))
            if cur.rowcount==0:error(404,"对比记录不存在。")
        return {"ok":True}
    @router.get("/me/export")
    def export_personal_data(request:Request,response:Response):
        s=required(request)
        response.headers["Cache-Control"]="no-store"
        response.headers["Content-Disposition"]='attachment; filename="b2b-atlas-personal-export.json"'
        return {"version":1,"exported_at":now(),"user":public_user(s),"library":library_data(s["user_id"]),
                "notice":"仅包含该账户的公开资料字段和私人收藏内容，不包含密码、登录令牌或其他用户资料。"}
    @router.post("/auth/request-password-reset")
    def request_password_reset(data:ResetRequest,request:Request):
        origin(request);ensure_ready()
        if not RESET_EMAIL_ENABLED:
            error(503,"邮箱服务尚未配置，请联系网站管理员处理密码重置。")
        limit(request,"password-reset",5,3600)
        with db() as conn:
            account=conn.one("SELECT id,email FROM atlas_users WHERE email=?",(data.email,))
        if account:
            token=secrets.token_urlsafe(48)
            with db() as conn:
                conn.execute("DELETE FROM atlas_password_resets WHERE user_id=?",(account["id"],))
                expiry=(datetime.now(timezone.utc)+timedelta(minutes=20)).isoformat(timespec="seconds")
                conn.execute("INSERT INTO atlas_password_resets(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                             (sha(token),account["id"],expiry,now()))
            try:send_reset_email(account["email"],token)
            except Exception:error(503,"邮件发送暂时失败，请稍后再试。")
        return {"ok":True,"message":"如果邮箱已注册，重置邮件将在稍后发送。"}
    @router.post("/auth/reset-password")
    def reset_password(data:ResetComplete,request:Request):
        origin(request);ensure_ready()
        limit(request,"reset-complete",12,900)
        with db() as conn:
            row=conn.one("SELECT user_id,expires_at FROM atlas_password_resets WHERE token_hash=?",(sha(data.token),))
            if not row or row["expires_at"]<=now():
                error(400,"链接无效或已经过期。")
            conn.execute("UPDATE atlas_users SET password_hash=?,updated_at=? WHERE id=?",
                         (hash_password(data.new_password),now(),row["user_id"]))
            conn.execute("DELETE FROM atlas_sessions WHERE user_id=?",(row["user_id"],))
            conn.execute("DELETE FROM atlas_password_resets WHERE user_id=?",(row["user_id"],))
        return {"ok":True}
    app.include_router(router)
