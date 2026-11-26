#!/usr/bin/env python3
"""Read-only live preview smoke test. No credentials, user creation or mutations."""
from __future__ import annotations

import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(NoRedirect)
ORIGIN = os.environ.get("PREVIEW_URL", "https://b2b-design-atlas-preview.onrender.com").rstrip("/")
EXPECTED = os.environ.get("EXPECTED_SHA", "").strip().lower()
RESULTS = []


def check(condition: bool, description: str):
    RESULTS.append((bool(condition), description))
    if not condition:
        print("::error::" + description)
    else:
        print("PASS " + description)


def fetch(path: str):
    request = Request(
        ORIGIN + path,
        headers={"Accept": "application/json,text/html,*/*",
                 "Cache-Control": "no-cache",
                 "User-Agent": "Atlas-Preview-Smoke/1.0"},
        method="GET",
    )
    try:
        with OPENER.open(request, timeout=25) as response:
            return response.status, response.headers, response.read(262144)
    except HTTPError as error:
        with error:
            return error.code, error.headers, error.read(2048)


def as_json(body):
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


def main():
    parsed = urlparse(ORIGIN)
    if parsed.scheme != "https" or parsed.netloc != "b2b-design-atlas-preview.onrender.com":
        raise SystemExit("Refusing unexpected smoke-test target")
    if not re.fullmatch(r"[0-9a-f]{40}", EXPECTED):
        raise SystemExit("EXPECTED_SHA must be the 40-character GitHub commit")

    status, headers, body = fetch("/api/atlas-build")
    build = as_json(body)
    check(status == 200, "deployment fingerprint endpoint returns 200")
    check(build.get("commit") == EXPECTED, "live deployment SHA matches tested commit")
    check(bool(re.fullmatch(r"V[0-9]+(?:\.[0-9]+){1,2}", str(build.get("cms_version", "")))),
          "CMS release version is available")
    check("no-store" in headers.get("Cache-Control", ""), "deployment metadata cannot be cached")
    check("Set-Cookie" not in headers, "version endpoint never creates a session")

    status, _, _ = fetch("/api/health")
    check(status == 200, "application health endpoint returns 200")

    status, _, body = fetch("/")
    check(status == 200 and bool(body.strip()), "public homepage is accessible")

    status, _, body = fetch("/api/auth/me")
    me = as_json(body)
    check(status == 200 and me.get("authenticated") is False and me.get("user") is None
          and "csrf_token" not in me, "anonymous session is not authenticated")

    status, _, body = fetch("/api/auth/status")
    auth = as_json(body)
    check(status == 200 and auth.get("available") is True,
          "registration/login persistence is ready (auth status)")
    if auth.get("mode") == "demo":
        print("::warning::Auth reports demo persistence; user data may not survive restart")

    for path, expected_next in (
        ("/admin", "/admin"),
        ("/admin/content", "/admin/content"),
    ):
        status, headers, _ = fetch(path)
        location = headers.get("Location", "")
        destination = urlparse(location)
        matches_redirect = (status in (302, 303, 307, 308)
                            and destination.path == "/login"
                            and parse_qs(destination.query).get("next") == [expected_next])
        check(matches_redirect, f"anonymous {path} redirects to login")
        check("no-store" in headers.get("Cache-Control", ""),
              f"anonymous {path} response is not cached")

    for path in (
        "/api/admin/overview",
        "/api/admin/content?kind=site",
        "/api/admin/media",
        "/api/admin/tags",
    ):
        status, _, _ = fetch(path)
        check(status == 401, f"anonymous {path.split('?')[0]} denies private data (401)")

    for path, expected_type in (
        ("/assets/cms.js", "javascript"),
        ("/assets/cms.css", "css"),
    ):
        status, headers, body = fetch(path)
        check(status == 200 and expected_type in headers.get("Content-Type", "").lower()
              and len(body) > 100,
              f"CMS {path.rsplit('.', 1)[-1].upper()} resource loads with correct content type")

    failures = sum(not ok for ok, _ in RESULTS)
    print(f"Live smoke: {len(RESULTS)-failures}/{len(RESULTS)} checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (TimeoutError, URLError, OSError) as exc:
        print(f"::error::Could not reach live preview: {type(exc).__name__}: {exc}")
        sys.exit(1)
