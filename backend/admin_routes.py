"""B2B Atlas V46 — real, read-only operations overview.

Admin API access is explicitly bound to existing authenticated user IDs
via ATLAS_ADMIN_USER_IDS.  An email address alone never grants admin status
because the current registration system has no email verification.

The public preview contains ONLY public catalog counts and readiness data.
It cannot see accounts, saved items, session data or administration actions.
"""
from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from app import seo_routes
from app import user_auth
from app import cms_access

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
ADMIN_IDS = {
    val.lower().strip()
    for val in os.getenv("ATLAS_ADMIN_USER_IDS", "").split(",")
    if re.fullmatch(r"[0-9a-fA-F-]{36}", val.strip())
}

def safe_slug(value):
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,110}", str(value or "")))

def safe_image(slug):
    if not safe_slug(slug):
        return None
    rel = Path("screenshots") / "sites" / (slug + ".webp")
    return "/" + rel.as_posix() if (ROOT / rel).is_file() else None

def public_metrics():
    catalog = seo_routes.catalog()
    sites = list(catalog["sites"].values())
    modules = list(catalog["modules"].values())
    patterns = list(catalog["patterns"].values())
    articles = list(catalog["articles"].values())
    research = seo_routes.read_json(STATIC / "assets" / "research.json", {})
    if not isinstance(research, dict):
        research = {}
    reviewed = set()
    for x in sites:
        slug = x.get("id", "")
        p = research.get(slug, {})
        if isinstance(p, dict) and p.get("checked"):
            reviewed.add(slug)
    shots = {x.get("id"): safe_image(x.get("id")) for x in sites}
    categories = Counter(str(x.get("sector") or "未分类") for x in sites)
    sectors = [{"name": name, "count": count} for name, count in categories.most_common(9)]
    queue = []
    for x in sorted(sites, key=lambda it: (bool(shots.get(it.get("id"))), str(it.get("name", "")))):
        slug = x.get("id", "")
        if slug in reviewed or not safe_slug(slug):
            continue
        queue.append({
            "id": slug,
            "name": str(x.get("name") or slug)[:90],
            "sector": str(x.get("sector") or "未分类")[:75],
            "thumbnail": shots.get(slug),
            "status": "需要截图检查" if not shots.get(slug) else "待补充研究",
            "url": "/websites/" + slug
        })
    recent = sorted(articles, key=lambda a: str(a.get("published_at") or a.get("date") or ""), reverse=True)
    recent = [{
        "title": str(a.get("title") or a.get("id") or "")[:160],
        "id": str(a.get("id") or ""),
        "date": str(a.get("published_at") or a.get("date") or "")[:10],
        "category": str(a.get("category") or "研究文章")[:60],
        "url": "/insights/" + str(a.get("id") or "")
    } for a in recent[:5] if safe_slug(a.get("id"))]
    totals = {
        "websites": len(sites),
        "sections": len(modules),
        "patterns": len(patterns),
        "insights": len(articles)
    }
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": totals,
        "review": {
            "reviewed": len(reviewed),
            "pending": max(0, len(sites) - len(reviewed)),
            "shots_ready": sum(1 for x in sites if shots.get(x.get("id"))),
            "shots_missing": sum(1 for x in sites if not shots.get(x.get("id")))
        },
        "sectors": sectors,
        "queue": queue[:100],
        "recent_articles": recent,
        "content_mix": [
            {"name":"Websites","value":totals["websites"],"key":"websites"},
            {"name":"Sections","value":totals["sections"],"key":"sections"},
            {"name":"Patterns","value":totals["patterns"],"key":"patterns"},
            {"name":"Insights","value":totals["insights"],"key":"insights"}
        ],
    }

def private_activity():
    user_auth.ensure_ready()
    today = datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=29)).isoformat()
    dates = [(today - timedelta(days=x)).isoformat() for x in range(29, -1, -1)]
    with user_auth.db() as conn:
        def count(table, where=""):
            row = conn.one("SELECT COUNT(*) AS n FROM " + table + (" WHERE " + where if where else ""))
            return int(row["n"]) if row else 0
        totals = {
            "users": count("atlas_users"),
            "saves": count("atlas_user_items", "collection='saved'") + count("atlas_user_entities", "collection='saved'"),
            "boards": count("atlas_user_items", "collection='board'") + count("atlas_user_entities", "collection='board'"),
            "folders": count("atlas_user_folders"),
            "comparisons": count("atlas_user_comparisons")
        }
        users = conn.all(
            "SELECT substr(created_at,1,10) AS day, COUNT(*) AS n FROM atlas_users "
            "WHERE created_at>=? GROUP BY substr(created_at,1,10)",
            (cutoff,)
        )
        primary = conn.all(
            "SELECT substr(created_at,1,10) AS day, COUNT(*) AS n FROM atlas_user_items "
            "WHERE collection='saved' AND created_at>=? GROUP BY substr(created_at,1,10)",
            (cutoff,)
        )
        secondary = conn.all(
            "SELECT substr(created_at,1,10) AS day, COUNT(*) AS n FROM atlas_user_entities "
            "WHERE collection='saved' AND created_at>=? GROUP BY substr(created_at,1,10)",
            (cutoff,)
        )
    def group(rows):
        return {r["day"]: int(r["n"]) for r in rows}
    reg = group(users); a = group(primary); b = group(secondary)
    return {"totals": totals, "activity": [
        {"date": day,"users":reg.get(day,0),"saves":a.get(day,0)+b.get(day,0)} for day in dates
    ]}

def admin_allowed(session):
    return bool(session and session.get("user_id", "").lower() in ADMIN_IDS)

def html_page(mode, template="admin.html"):
    doc = (STATIC / template).read_text(encoding="utf-8")
    doc = doc.replace("__ADMIN_MODE__", mode)
    headers = {
        "Cache-Control": "no-store",
        "X-Robots-Tag": "noindex, nofollow",
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'"
        )
    }
    return HTMLResponse(doc, headers=headers)

def register_admin_routes(app: FastAPI):
    @app.get("/admin/preview", include_in_schema=False)
    def preview_page(request: Request):
        """Retired public-lookalike admin page: route through real login gate."""
        return RedirectResponse("/admin",status_code=302,
                                headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex"})

    @app.get("/admin", include_in_schema=False)
    def admin_page(request: Request):
        session = user_auth.session(request)
        if not session:
            return RedirectResponse("/login?next=%2Fadmin", status_code=302,
                                    headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex"})
        if not admin_allowed(session):
            return HTMLResponse(
                '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
                '<meta name="robots" content="noindex"><title>权限不足 · B2B Atlas</title>'
                '<body style="font-family:system-ui;background:#f5f7fc;color:#172642;'
                'margin:15vh auto;max-width:520px;padding:25px"><h1>此账号没有后台权限</h1>'
                '<p>后台仅向已授权的管理员开放。普通账户仍可以使用个人收藏与研究板。</p>'
                '<p>请让站点所有者在 Render 环境变量 ATLAS_ADMIN_USER_IDS 中配置'
                '管理员账号的用户 ID。</p><a href="/account">返回个人中心 ↗</a></body></html>',
                status_code=403,
                headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex"}
            )
        return html_page("admin")

    @app.get("/admin/content/preview", include_in_schema=False)
    def content_preview_page(request: Request):
        """Retired public-lookalike CMS screen; use protected content studio."""
        return RedirectResponse("/admin/content",status_code=302,
                                headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex"})

    @app.get("/admin/content", include_in_schema=False)
    def content_admin_page(request: Request):
        session=user_auth.session(request)
        if not session:
            return RedirectResponse("/login?next=%2Fadmin%2Fcontent",status_code=302,
                                    headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex"})
        if not cms_access.can(session,'view'):
            return HTMLResponse("<h1>403 · 需要管理员权限</h1><p>此账户尚未获得后台管理授权。</p>"
                                '<p><a href="/account">返回个人中心</a></p>',
                                status_code=403,headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex"})
        doc=(STATIC/"cms.html").read_text(encoding="utf-8").replace("__CMS_MODE__","admin")
        headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex, nofollow",
            "Content-Security-Policy":(
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")}
        return HTMLResponse(doc,headers=headers)

    @app.get("/api/admin/preview", include_in_schema=False)
    def preview_metrics(request: Request,response: Response):
        """Legacy preview metadata is not public admin API anymore."""
        session=user_auth.required(request)
        if not admin_allowed(session):user_auth.error(403,"需要管理员权限。")
        response.headers["Cache-Control"] = "no-store"
        data = public_metrics()
        data["mode"] = "preview"
        data["private"] = None
        data["email_reset_enabled"] = None
        return data

    @app.get("/api/admin/overview", include_in_schema=False)
    def admin_overview(request: Request, response: Response):
        # 401 for guests, 403 for unassigned accounts. Never infer admin
        # permission from an unverified email, query argument or localStorage.
        session = user_auth.required(request)
        if not admin_allowed(session):
            user_auth.error(403, "此账户没有管理员权限。")
        response.headers["Cache-Control"] = "no-store"
        data = public_metrics()
        data["mode"] = "admin"
        data["private"] = private_activity()
        data["email_reset_enabled"] = user_auth.RESET_EMAIL_ENABLED
        data["administrator"] = {
            "name": session["display_name"],
            "email": session["email"]
        }
        return data
