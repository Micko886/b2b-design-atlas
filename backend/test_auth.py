"""Account regression tests; run with PYTHONPATH=backend python backend/test_auth.py."""
import os, tempfile
path=os.path.join(tempfile.gettempdir(),"atlas-v40-test-"+str(os.getpid())+".db")
os.environ["ATLAS_ALLOW_EPHEMERAL_AUTH"]="1"
os.environ["ATLAS_USERS_DB_PATH"]=path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from user_auth import register_auth_routes

app=FastAPI()
register_auth_routes(app)
a=TestClient(app,base_url="https://testserver")
b=TestClient(app,base_url="https://testserver")
def check(response,status):
    assert response.status_code==status,(response.status_code,response.text)
    return response.json()
def signup(client,email):
    return check(client.post("/api/auth/register",json={"email":email,"display_name":"QA User","password":"long-test-password-123"}),201)
sa=signup(a,"qa-a@example.test")
assert sa["authenticated"] and sa["csrf_token"]
assert "atlas_session" in a.cookies
headers={"X-CSRF-Token":sa["csrf_token"]}
assert check(a.get("/api/auth/me"),200)["authenticated"]
check(a.post("/api/me/library",json={"collection":"saved","key":"site:vast"}),403)
check(a.post("/api/me/library",json={"collection":"saved","key":"site:vast"},headers=headers),201)
check(a.post("/api/me/library",json={"collection":"board","key":"module:vast-hero"},headers=headers),201)
check(a.patch("/api/me/library/note",json={"key":"module:vast-hero","note":"Good visual hierarchy"},headers=headers),200)
lib=check(a.get("/api/me/library"),200)
assert lib["saved"]==["site:vast"],lib
assert lib["board"]==["module:vast-hero"],lib
assert lib["notes"]["module:vast-hero"]=="Good visual hierarchy"
sb=signup(b,"qa-b@example.test")
assert check(b.get("/api/me/library"),200)["saved"]==[]
check(a.post("/api/auth/change-password",json={"current_password":"wrong","new_password":"new-long-password-123"},headers=headers),400)
check(a.post("/api/auth/change-password",json={"current_password":"long-test-password-123","new_password":"new-long-password-123"},headers=headers),200)
check(a.post("/api/auth/logout",headers=headers),200)
assert not check(a.get("/api/auth/me"),200)["authenticated"]
check(a.post("/api/auth/login",json={"email":"qa-a@example.test","password":"long-test-password-123"}),401)
new=check(a.post("/api/auth/login",json={"email":"qa-a@example.test","password":"new-long-password-123"}),200)
headers={"X-CSRF-Token":new["csrf_token"]}
assert check(a.get("/api/me/library"),200)["saved"]==["site:vast"]
check(a.delete("/api/me/library/saved/site/vast",headers=headers),200)
assert check(a.get("/api/me/library"),200)["saved"]==[]
check(b.post("/api/me/library",json={"collection":"saved","key":"site:vast"},headers={"X-CSRF-Token":sb["csrf_token"]}),201)
assert check(a.get("/api/me/library"),200)["saved"]==[]
assert check(b.get("/api/me/library"),200)["saved"]==["site:vast"]
check(a.post("/api/me/library",json={"collection":"saved","key":"NOT_VALID"},headers=headers),422)
print("AUTH_V40_QA_PASS: register, login, cookie, CSRF, collection isolation, notes, logout, password change")


# V43: independent collections, four resource kinds, annotations, personal export.
from urllib.parse import quote
ha={"X-CSRF-Token":new["csrf_token"]}
hb={"X-CSRF-Token":sb["csrf_token"]}
pa=check(a.post("/api/me/library",json={"collection":"saved","key":"pattern:object-first-hero"},headers=ha),201)
aa=check(a.post("/api/me/library",json={"collection":"saved","key":"article:b2b-homepage-value-proposition"},headers=ha),201)
folder=check(a.post("/api/me/folders",json={"name":"工业官网项目","color":"#315BE8"},headers=ha),201)
fid=folder["id"]
assert folder["name"]=="工业官网项目"
check(a.post("/api/me/library",json={"collection":"saved","key":"site:vast"},headers=ha),201)
check(a.post("/api/me/folders/"+fid+"/items",json={"key":"site:vast"},headers=ha),201)
check(a.post("/api/me/folders/"+fid+"/items",json={"key":"pattern:object-first-hero"},headers=ha),201)
check(a.patch("/api/me/library/annotation",json={"key":"site:vast","note":"Dark cinematic imagery","tags":["工程","首屏"]},headers=ha),200)
current=check(a.get("/api/me/library"),200)
assert len(current["folders"])==1,current
assert len(current["folderItems"][fid])==2,current
assert current["annotations"]["site:vast"]["note"]=="Dark cinematic imagery"
assert "pattern:object-first-hero" in current["saved"]
assert "article:b2b-homepage-value-proposition" in current["saved"]
assert check(b.get("/api/me/library"),200)["folders"]==[]
check(b.post("/api/me/folders/"+fid+"/items",json={"key":"site:vast"},headers=hb),404)
check(b.patch("/api/me/folders/"+fid,json={"name":"hijacked"},headers=hb),404)
check(b.delete("/api/me/folders/"+fid,headers=hb),404)
dump=check(a.get("/api/me/export"),200)
assert dump["library"]["annotations"]["site:vast"]["tags"]==["工程","首屏"]
assert "password" not in str(dump).lower() and "token" not in str(dump).lower()
check(a.patch("/api/me/folders/"+fid,json={"name":"航天项目","color":"#0D306E"},headers=ha),200)
check(a.delete("/api/me/folders/"+fid,headers=ha),200)
assert "site:vast" in check(a.get("/api/me/library"),200)["saved"],"Deleting a folder must retain saved item"
guest=TestClient(app,base_url="https://testserver")
assert guest.get("/api/me/export").status_code==401
assert guest.post("/api/me/folders",json={"name":"bad"}).status_code==401
assert a.post("/api/me/folders",json={"name":"no-csrf"}).status_code==403
print("V43_QA_PASS: 4 resource kinds, folder CRUD, per-user isolation, tags, notes and privacy export")
