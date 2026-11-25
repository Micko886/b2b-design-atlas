"""Ensure the legacy backend cannot bypass authenticated V46 /admin."""
from pathlib import Path
import tarfile
from install_auth import patch_main, LEGACY_ADMIN, SPA

archive=Path(__file__).resolve().parents[1]/"atlas-source-v23.tar.gz"
with tarfile.open(archive,"r:gz") as tar:
    member=tar.extractfile("./app/main.py")
    assert member is not None
    src=member.read().decode("utf-8")
assert src.count(LEGACY_ADMIN)==1, "Source archive changed; review before deploying"
patched=patch_main(src)
assert LEGACY_ADMIN not in patched, "Legacy unprotected route remains"
assert "from app.admin_routes import register_admin_routes" in patched
assert "register_admin_routes(app)" in patched
assert patched.index("register_admin_routes(app)")<patched.index(SPA)
assert patched.count('return seo_document(full_path)')==1
assert "return FileResponse(STATIC / \"admin.html\")" not in patched
print("V46_INSTALL_QA_PASS: raw unprotected /admin removed; protected admin registered before catch-all")
