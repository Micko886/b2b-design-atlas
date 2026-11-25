"""Owner-controlled CMS team permissions and audit history."""
from __future__ import annotations
import re
import uuid
from fastapi import FastAPI,Request
from pydantic import BaseModel
from typing import Literal
from app import cms_access,user_auth

USER_ID=re.compile(r"^[0-9a-fA-F-]{36}$")
class RoleGrant(BaseModel):
    user_id: str
    role: Literal["editor","reviewer"]

def owner(request,mutate=False):
    session=user_auth.required(request)
    cms_access.require(session,"team")
    if mutate:
        user_auth.origin(request)
        user_auth.check_csrf(request,session)
    return session

def register_team_routes(app:FastAPI):
    @app.get("/api/admin/team/me",include_in_schema=False)
    def my_cms_role(request:Request):
        session=user_auth.required(request)
        cms_access.require(session,"view")
        return cms_access.describe(session)

    @app.get("/api/admin/team",include_in_schema=False)
    def list_team(request:Request):
        owner(request);cms_access.ensure_roles()
        with user_auth.db() as db:
            people=db.all("""SELECT u.id,u.email,u.display_name,u.created_at,
                        r.role,r.updated_at
                        FROM atlas_users u LEFT JOIN atlas_cms_roles r ON r.user_id=u.id
                        ORDER BY u.created_at DESC LIMIT 250""")
            history=db.all("""SELECT user_id,role,action,actor_id,created_at
                         FROM atlas_cms_role_history ORDER BY created_at DESC LIMIT 35""")
        for person in people:
            if person["id"].lower() in cms_access.OWNER_IDS:person["role"]="owner"
        return {"people":people,"history":history,
                "roles":["owner","editor","reviewer"],
                "note":"最高管理员由 Render 环境变量授权；这里仅能管理编辑和审核角色。" }

    @app.put("/api/admin/team/role",include_in_schema=False)
    def set_role(data:RoleGrant,request:Request):
        session=owner(request,mutate=True);cms_access.ensure_roles()
        try:user_id=str(uuid.UUID(data.user_id))
        except (ValueError,TypeError):user_auth.error(422,"用户 ID 无效。")
        if user_id.lower() in cms_access.OWNER_IDS:
            user_auth.error(409,"环境变量授权的最高管理员无法在这里降级。")
        with user_auth.db() as db:
            person=db.one("SELECT id FROM atlas_users WHERE id=?",(user_id,))
            if not person:user_auth.error(404,"用户不存在，请从已注册用户中选择。")
            now=user_auth.now()
            db.execute("""INSERT INTO atlas_cms_roles(user_id,role,granted_by,updated_at)
                VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                role=excluded.role,granted_by=excluded.granted_by,updated_at=excluded.updated_at""",
                (user_id,data.role,session["user_id"],now))
            db.execute("""INSERT INTO atlas_cms_role_history
                (id,user_id,action,role,actor_id,created_at) VALUES(?,?,?,?,?,?)""",
                (str(uuid.uuid4()),user_id,"grant",data.role,session["user_id"],now))
        return {"ok":True,"user_id":user_id,"role":data.role}

    @app.delete("/api/admin/team/role/{user_id}",include_in_schema=False)
    def revoke_role(user_id:str,request:Request):
        session=owner(request,mutate=True);cms_access.ensure_roles()
        try:uid=str(uuid.UUID(user_id))
        except (ValueError,TypeError):user_auth.error(422,"用户 ID 无效。")
        if uid.lower() in cms_access.OWNER_IDS:
            user_auth.error(409,"无法移除环境变量授权的最高管理员。")
        with user_auth.db() as db:
            record=db.one("SELECT role FROM atlas_cms_roles WHERE user_id=?",(uid,))
            if not record:user_auth.error(404,"该用户没有额外后台角色。")
            db.execute("DELETE FROM atlas_cms_roles WHERE user_id=?",(uid,))
            db.execute("""INSERT INTO atlas_cms_role_history
                (id,user_id,action,role,actor_id,created_at) VALUES(?,?,?,?,?,?)""",
                (str(uuid.uuid4()),uid,"revoke",record["role"],session["user_id"],user_auth.now()))
        return {"ok":True,"user_id":uid}
