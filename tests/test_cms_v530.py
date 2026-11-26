"""V53.0 navigation, cross-kind review queue and admin permission regressions."""
import re
import unittest
from pathlib import Path

STATIC=Path("/srv/atlas/static")
PRIMARY=("工作台","内容管理","媒体资源","审核发布","运营中心","系统设置")


class V530WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin=(STATIC/"admin.html").read_text(encoding="utf-8")
        cls.cms=(STATIC/"cms.html").read_text(encoding="utf-8")
        cls.js=(STATIC/"assets/cms.js").read_text(encoding="utf-8")
        cls.admin_js=(STATIC/"assets/admin.js").read_text(encoding="utf-8")
        cls.css=(STATIC/"assets/cms.css").read_text(encoding="utf-8")
        cls.admin_css=(STATIC/"assets/admin.css").read_text(encoding="utf-8")
        cls.browser=Path("/srv/atlas/tests/browser/cms-v525.spec.mjs").read_text(encoding="utf-8")

    def test_six_primary_destinations_match_both_pages(self):
        for page in (self.admin,self.cms):
            segment=page.split('<nav class="side-nav atlas-v521-nav atlas-v530-nav"',1)[1].split("</nav>",1)[0]
            for name in PRIMARY:
                with self.subTest(page="admin" if page is self.admin else "cms",name=name):
                    self.assertEqual(segment.count("<span>"+name+"</span>"),1)
            self.assertIn('href="/"',segment)
        self.assertIn("atlas-v530-nav",self.admin_css)

    def test_settings_and_media_are_single_destinations_with_unique_ids(self):
        for id in ("cms-review-shortcut","cms-media-open","cms-schedules-open",
                   "cms-settings-open","cms-review-dialog","cms-review-queue",
                   "cms-settings-dialog","cms-tools-menu","cms-categories-open",
                   "cms-tags-open","cms-team-open","cms-export"):
            with self.subTest(id=id):
                self.assertEqual(self.cms.count('id="'+id+'"'),1)
        self.assertIn('id="cms-settings-open" class="side-link',self.cms)
        self.assertIn('id="cms-media-open" class="side-link',self.cms)
        self.assertIn('cms-v530-settings-tools',self.cms)

    def test_review_queue_fetches_all_four_types_and_handles_partial_failures(self):
        self.assertIn("async function refreshReviewQueue()",self.js)
        self.assertIn("Object.keys(kinds)",self.js)
        self.assertIn("Promise.allSettled(types.map(kind=>api('/api/admin/content?kind='+kind))",self.js)
        self.assertIn("out.value.items.filter(x=>x.status==='review')",self.js)
        self.assertIn("部分栏目读取失败",self.js)
        self.assertIn("data-review-open-kind",self.js)
        self.assertIn("data-review-open-slug",self.js)
        self.assertIn("async function openReviewRecord(kind,slug)",self.js)
        self.assertIn("if(state.selected?.slug!==slug||state.selected?.kind!==kind)return",self.js)
        self.assertIn("setEditorTab('review')",self.js)

    def test_permission_checks_precede_sensitive_ui_actions(self):
        self.assertIn("if(!can('view')){message('当前账号没有内容查看权限。'",self.js)
        self.assertIn("if(!(can('taxonomy')||can('team')||can('export')))",self.js)
        self.assertIn("$('#cms-settings-open').hidden=!(can('taxonomy')",self.js)
        self.assertIn("$('#cms-media-open').hidden=!can('media')",self.js)
        self.assertIn("$('#cms-review-shortcut').hidden=!can('view')",self.js)
        self.assertIn("$('#cms-tools-menu').hidden=true",self.js)
        self.assertIn('data-owner-only hidden',self.cms)

    def test_media_schedule_review_settings_are_valid_deep_links(self):
        for item in ("media","review","schedule","settings"):
            with self.subTest(item=item):
                self.assertIn("routeParams.get('workspace')==='"+item+"'",self.js)
                self.assertIn("workspace="+item,self.admin)
        for kind in ("site","module","pattern","article"):
            self.assertIn(kind+":{title:",self.js)
        self.assertIn("markWorkspace('operations')",self.js)

    def test_content_editor_and_mobile_responsiveness_preserved(self):
        self.assertIn("function setStudioMode(editing)",self.js)
        self.assertIn("root.innerHTML=topbar+siteHeader+rejectionNote+tabs",self.js)
        self.assertIn("@media(max-width:600px)",self.css)
        self.assertIn(".cms-v530-review-row",self.css)
        self.assertIn(".cms-v530-settings-tools",self.css)
        self.assertIn(".atlas-v530-nav",self.admin_css)

    def test_first_autosave_unlocks_submit_after_busy_state(self):
        self.assertIn("function syncBusyButtonState(button,disabled)",self.js)
        self.assertIn("if(state.busy)button.dataset.cmsBeforeBusy=disabled?'1':'0'",self.js)
        self.assertIn("button.disabled=state.busy?true:disabled",self.js)
        self.assertIn("syncBusyButtonState($('[data-editor-submit]'),false)",self.js)
        self.assertIn("button.disabled=button.dataset.cmsBeforeBusy==='1'",self.js)
        self.assertIn("site editor autosaves and reviewer transitions work",self.browser)

    def test_browser_regression_includes_navigation_roles_and_no_db_writes(self):
        for term in ("V53.0 unified review inbox opens all four types",
                     "V53.0 media and settings are separate role-gated entries",
                     "V53.0 low-privilege roles cannot open settings",
                     "V53.0 admin and CMS navigation share six labels",
                     "no production writes"):
            with self.subTest(term=term):
                self.assertIn(term,self.browser)

    def test_versions_are_explicit_for_all_shell_assets(self):
        for value in ("admin.css?v=5300",):
            self.assertIn(value,self.cms)
        self.assertRegex(self.cms,r"cms\.js\?v=\d{4,}")
        self.assertRegex(self.cms,r"cms\.css\?v=\d{4,}")
        for value in ("admin.js?v=5300","admin.css?v=5300"):
            self.assertIn(value,self.admin)

    def test_no_single_dom_selector_iteration(self):
        for pattern in (r"(?<!\$)\$\([^)]*\)\.forEach",r"for\s*\([^)]*\bof\s+\$\("):
            self.assertFalse(re.search(pattern,self.js))


if __name__=="__main__":
    unittest.main()
