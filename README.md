# B2B Design Atlas (preview v0.2)

FastAPI + SQLite reference-library pilot. Starter data includes fictional design studies, not verified third-party sites.

Deploy: Render Docker service, built from atlas-source.tar.gz. The archive contains app, static, run.py and requirements.txt.

Local: extract archive and run pip install -r requirements.txt && python run.py.

Public admin write operations are disabled by default: ATLAS_ADMIN_TOKEN is not configured. This demo uses ephemeral SQLite storage, not production-grade durable persistence.
