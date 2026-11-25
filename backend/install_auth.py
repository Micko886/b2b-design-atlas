"""Install auth, SEO and protected V46 admin routes into the bundled backend.

Legacy atlas-source-v23 defines /admin as an *unprotected* static HTML route.
It MUST be removed before registering V46's authenticated /admin entry.
"""
from pathlib import Path

TARGET=Path("/srv/atlas/app/main.py")
SPA='@app.get("/{full_path:path}",include_in_schema=False)'
LEGACY_ADMIN='@app.get("/admin")\ndef admin_page(): return FileResponse(STATIC / "admin.html")'
HTML_RESPONSE='return FileResponse(STATIC / "index.html")'

def patch_main(source: str) -> str:
    if source.count(SPA)!=1:
        raise RuntimeError("SPA catch-all changed; cannot safely install V46 routes")
    if source.count(LEGACY_ADMIN)!=1:
        raise RuntimeError("Legacy unprotected admin handler changed; abort protected routing")
    if source.count(HTML_RESPONSE)!=1:
        raise RuntimeError("SPA response changed; abort protected routing")

    # Delete the unprotected handler first. Routes are matched in registration
    # order and an earlier @app.get('/admin') would bypass V46 protection.
    source=source.replace(LEGACY_ADMIN, "# Legacy unprotected /admin route disabled by V46",1)
    extra=(
        "from app.user_auth import register_auth_routes\n"
        "register_auth_routes(app)\n"
        "from app.seo_routes import register_seo_routes, seo_document\n"
        "register_seo_routes(app)\n"
        "from app.admin_routes import register_admin_routes\n"
        "register_admin_routes(app)\n"
        "from app.cms_routes import register_cms_routes\n"
        "register_cms_routes(app)\n\n"
    )
    source=source.replace(SPA,extra+SPA,1)
    source=source.replace(HTML_RESPONSE,"return seo_document(full_path)",1)
    return source

if __name__=="__main__":
    source=TARGET.read_text(encoding="utf-8")
    TARGET.write_text(patch_main(source),encoding="utf-8")
