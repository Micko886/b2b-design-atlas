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
