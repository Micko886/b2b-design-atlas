# B2B Design Atlas — v0.2 Preview

B2B website design inspiration library, original concept studies, section gallery, layout patterns, and local design board.

## Deployment
Git-backed Render Docker service. Dockerfile unpacks `atlas-source.tar.xz` and starts FastAPI on Render's assigned `PORT`.

- `/`: design gallery and board
- `/api/health`: health check
- `/api/stats`: content counts

The editorial write endpoints are disabled until `ATLAS_ADMIN_TOKEN` is configured. The free preview has an ephemeral SQLite database. Do not use it for persistent content management or user accounts.

**The starter designs are fictional original studies, not sourced real company websites.**
