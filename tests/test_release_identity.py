"""Regression gate: public version endpoint reports only safe deployment metadata."""
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI, Response
from app import admin_routes


class ReleaseIdentityTests(unittest.TestCase):
    def test_fingerprint_is_current_and_only_contains_version_and_sha(self):
        sha="a"*40
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(admin_routes,"STATIC",Path(tmp)), \
             patch.dict(os.environ,{"RENDER_GIT_COMMIT":sha}):
            (Path(tmp)/"cms.html").write_text(
                '<span class="brand-version">V54.2</span>',encoding="utf-8"
            )
            app=FastAPI()
            admin_routes.register_admin_routes(app)
            endpoint=next(r.endpoint for r in app.routes
                          if getattr(r,"path","")=="/api/atlas-build")
            response=Response()
            payload=endpoint(response)
            self.assertEqual(payload,{"cms_version":"V54.2","commit":sha})
            self.assertEqual(response.headers["Cache-Control"],"no-store, max-age=0")

    def test_invalid_environment_commit_is_not_exposed(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(admin_routes,"STATIC",Path(tmp)), \
             patch.dict(os.environ,{"RENDER_GIT_COMMIT":"password=not-a-sha"}):
            (Path(tmp)/"cms.html").write_text(
                '<span class="brand-version">V54.2</span>',encoding="utf-8"
            )
            self.assertEqual(admin_routes.release_identity()["commit"],None)


if __name__=="__main__":
    unittest.main()
