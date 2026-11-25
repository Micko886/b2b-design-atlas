"""V51.21 · Unified admin shell, login-gated pages, editor views and regression contracts."""
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI,HTTPException
from app import admin_routes,cms_access,user_auth

STATIC=Path("/srv/atlas/static")

class AuthenticatedWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app=FastAPI()
        admin_routes.register_admin_routes(app)
        cls.routes={r.path:r.endpoint for r in app.routes if getattr(r,"path","").startswith("/admin") or
                   getattr(r,"path","")=="/api/admin/preview"}

    def test_public_admin_preview_now_redirects_to_login_gate(self):
        redirect=self.routes["/admin/preview"](object())
        self.assertEqual(redirect.status_code,302)
        self.assertEqual(redirect.headers["location"],"/admin")
        self.assertEqual(redirect.headers["cache-control"],"no-store")

    def test_public_cms_preview_now_redirects_to_login_gate(self):
        redirect=self.routes["/admin/content/preview"](object())
        self.assertEqual(redirect.status_code,302)
        self.assertEqual(redirect.headers["location"],"/admin/content")

    def test_guest_admin_redirects_to_login(self):
        with patch.object(user_auth,"session",return_value=None):
            page=self.routes["/admin"](object())
        self.assertEqual(page.status_code,302)
        self.assertIn("/login?",page.headers["location"])

    def test_guest_cms_redirects_to_login(self):
        with patch.object(user_auth,"session",return_value=None):
            page=self.routes["/admin/content"](object())
        self.assertEqual(page.status_code,302)
        self.assertIn("/login?",page.headers["location"])

    def test_signed_in_non_editor_cannot_open_cms(self):
        with patch.object(user_auth,"session",return_value={"user_id":"normal"}),\
             patch.object(cms_access,"can",return_value=False):
            page=self.routes["/admin/content"](object())
        self.assertEqual(page.status_code,403)
        self.assertIn("no-store",page.headers["cache-control"])

    def test_signed_in_non_owner_cannot_open_overview(self):
        with patch.object(user_auth,"session",return_value={"user_id":"normal"}),\
             patch.object(admin_routes,"admin_allowed",return_value=False):
            page=self.routes["/admin"](object())
        self.assertEqual(page.status_code,403)

    def test_retired_preview_metadata_endpoint_is_not_public(self):
        endpoint=self.routes["/api/admin/preview"]
        with patch.object(user_auth,"required",side_effect=HTTPException(401,"login")):
            with self.assertRaises(HTTPException) as error:
                endpoint(object(),object())
        self.assertEqual(error.exception.status_code,401)
        with patch.object(user_auth,"required",return_value={"user_id":"normal"}),\
             patch.object(admin_routes,"admin_allowed",return_value=False):
            with self.assertRaises(HTTPException) as error:
                endpoint(object(),object())
        self.assertEqual(error.exception.status_code,403)

    def test_authenticated_cms_uses_protected_html_and_no_store(self):
        with patch.object(user_auth,"session",return_value={"user_id":"editor"}),\
             patch.object(cms_access,"can",return_value=True):
            page=self.routes["/admin/content"](object())
        self.assertEqual(page.status_code,200)
        self.assertEqual(page.headers["cache-control"],"no-store")
        self.assertIn(b"atlas-v521-nav",page.body)
        self.assertIn(b"Content",page.body)

class UnifiedNavigationContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin=(STATIC/"admin.html").read_text(encoding="utf-8")
        cls.cms=(STATIC/"cms.html").read_text(encoding="utf-8")
        cls.admin_js=(STATIC/"assets/admin.js").read_text(encoding="utf-8")
        cls.cms_js=(STATIC/"assets/cms.js").read_text(encoding="utf-8")
        cls.app_js=(STATIC/"assets/app.js").read_text(encoding="utf-8")
        cls.admin_css=(STATIC/"assets/admin.css").read_text(encoding="utf-8")
        cls.cms_css=(STATIC/"assets/cms.css").read_text(encoding="utf-8")

    def test_both_pages_share_six_primary_workspaces(self):
        for name in ("工作台","内容管理","媒体资源","审核发布","运营中心","系统设置"):
            with self.subTest(name=name):
                self.assertIn(name,self.admin)
                self.assertIn(name,self.cms)
        self.assertIn("atlas-v530-nav",self.admin)
        self.assertIn("atlas-v530-nav",self.cms)

    def test_all_cms_action_ids_exist_once_and_belong_to_settings_or_sidebar(self):
        for action in ("cms-new","cms-refresh","cms-review-shortcut","cms-schedules-open",
                       "cms-media-open","cms-categories-open","cms-tags-open","cms-team-open",
                       "cms-export","cms-logout","cms-settings-open"):
            with self.subTest(action=action):
                self.assertEqual(self.cms.count('id="'+action+'"'),1)
        self.assertIn('id="cms-tools-menu" hidden',self.cms)
        self.assertIn("atlas-v521-quicknav",self.cms)

    def test_four_editor_tabs_and_html_panes_are_wired(self):
        for tab in ("content","seo","review","history"):
            self.assertIn('data-editor-tab="'+tab+'"',self.cms_js)
            self.assertIn('data-editor-pane="'+tab+'"',self.cms_js)
        self.assertIn("function setEditorTab(tab)",self.cms_js)
        self.assertIn("pane.hidden=pane.dataset.editorPane!==selected",self.cms_js)
        self.assertIn("role=\"tablist\"",self.cms_js)

    def test_settings_and_logout_fail_closed(self):
        self.assertIn("$('#cms-tools-menu').hidden=true",self.cms_js)
        self.assertIn("$('#cms-tools-menu').hidden=!(can('taxonomy')",self.cms_js)
        self.assertIn("$('#cms-settings-open').hidden=!(can('taxonomy')",self.cms_js)
        self.assertIn("async function logoutCms()",self.cms_js)
        self.assertIn("async function logoutAdmin()",self.admin_js)
        self.assertIn("'/api/auth/logout'",self.cms_js)
        self.assertIn("'/api/auth/logout'",self.admin_js)
        self.assertIn("X-CSRF-Token",self.admin_js)

    def test_no_remaining_single_element_for_each_crashes(self):
        for file,script in (("cms",self.cms_js),("admin",self.admin_js),("public",self.app_js)):
            with self.subTest(file=file):
                invalid=re.findall(r"(?<!\$)\$\([^)]*\)\.forEach",script)
                self.assertEqual(invalid,[])
                non_iterable=re.findall(r"for\s*\([^)]*\bof\s+\$\(",script)
                self.assertEqual(non_iterable,[])

    def test_review_queue_and_calendar_deep_links(self):
        for route in ("workspace=review","workspace=schedule","workspace=media","workspace=settings"):
            self.assertIn(route,self.admin)
        for workspace in ("review","schedule","media","settings"):
            self.assertIn("routeParams.get('workspace')==='"+workspace+"'",self.cms_js)
        self.assertIn("openReviewQueue()",self.cms_js)
        self.assertIn("openScheduleQueue()",self.cms_js)

    def test_workspace_highlight_tracks_editorial_context(self):
        self.assertIn("function markWorkspace(name)",self.cms_js)
        self.assertIn("markWorkspace('review')",self.cms_js)
        self.assertIn("markWorkspace('operations')",self.cms_js)
        self.assertIn("markWorkspace('content')",self.cms_js)
        self.assertIn("markWorkspace(state.status==='review'?'review':'content')",self.cms_js)
        self.assertIn('data-owner-only hidden',self.cms)

    def test_theme_and_responsive_layout_preserved(self):
        for html in (self.admin,self.cms):
            self.assertIn('data-set-theme="light"',html)
            self.assertIn('data-set-theme="dark"',html)
            self.assertNotIn('href="/admin/preview"',html)
        self.assertIn("@media(max-width:680px)",self.cms_css)
        self.assertIn("html[data-theme=dark]",self.admin_css)

    def test_updated_asset_versions(self):
        self.assertIn("admin.js?v=5300",self.admin)
        self.assertIn("admin.css?v=5300",self.admin)
        self.assertIn("cms.js?v=5300",self.cms)
        self.assertIn("cms.css?v=5300",self.cms)

if __name__=="__main__":
    unittest.main()
