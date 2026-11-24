"""Install auth and SEO routes ahead of the historical SPA catch-all."""
from pathlib import Path
path=Path("/srv/atlas/app/main.py")
source=path.read_text(encoding="utf-8")
anchor='@app.get("/{full_path:path}",include_in_schema=False)'
if source.count(anchor)!=1:
    raise SystemExit("SPA catch-all signature changed; abort patch")
extra=("from app.user_auth import register_auth_routes\n"
       "register_auth_routes(app)\n"
       "from app.seo_routes import register_seo_routes, seo_document\n"
       "register_seo_routes(app)\n\n")
source=source.replace(anchor,extra+anchor,1)
tail='return FileResponse(STATIC / "index.html")'
if source.count(tail)!=1:
    raise SystemExit("SPA response signature changed; abort patch")
source=source.replace(tail,"return seo_document(full_path)",1)
path.write_text(source,encoding="utf-8")
