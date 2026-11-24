"""Register authentication API routes before the SPA catch-all."""
from pathlib import Path
file=Path("/srv/atlas/app/main.py")
source=file.read_text()
anchor='@app.get("/{full_path:path}",include_in_schema=False)'
if source.count(anchor)!=1:raise SystemExit("Backend SPA signature changed; abort auth patch")
file.write_text(source.replace(anchor,'from app.user_auth import register_auth_routes\nregister_auth_routes(app)\n\n'+anchor))
