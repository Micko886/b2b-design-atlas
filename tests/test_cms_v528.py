"""V52.8 · Public dossier preview alignment and durable, failure-safe approval UI."""
import unittest
from pathlib import Path

ROOT=Path("/srv/atlas")
STATIC=ROOT/"static"


class PreviewAndReviewSafetyV528(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(STATIC/"assets/cms.js").read_text(encoding="utf-8")
        cls.css=(STATIC/"assets/cms.css").read_text(encoding="utf-8")
        cls.html=(STATIC/"cms.html").read_text(encoding="utf-8")
        cls.browser=(ROOT/"tests/browser/cms-v525.spec.mjs").read_text(encoding="utf-8")

    def test_detail_preview_uses_public_research_fields_and_image_first_layout(self):
        for expected in (
            "WEBSITE RESEARCH / 案例研究",
            "['业务方向',data.focus]",
            "['网站类型',data.model||'企业网站']",
            "cms-public-specs",
            "cms-public-style-tags",
            "cms-public-gallery-note",
            "前台保留的原有研究截图",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected,self.js)
        self.assertIn(".cms-public-detail-sample>.cms-public-gallery{grid-column:1;grid-row:1",self.css)
        self.assertIn(".cms-public-detail-sample>.cms-public-detail-info{grid-column:2;grid-row:1",self.css)
        self.assertIn("@media(max-width:840px)",self.css)
        self.assertIn(".cms-public-detail-sample>.cms-public-detail-info{grid-column:1;grid-row:2}",self.css)

    def test_busy_lock_uses_plural_selector_and_restores_original_disabled_state(self):
        segment=self.js[self.js.index("function btnDisable(value){"):
                        self.js.index("function setNotice(",self.js.index("function btnDisable(value){"))]
        self.assertIn("$$('[data-editor-pane] button",segment)
        self.assertNotIn(" $('[data-editor-pane] button",segment)
        self.assertIn("button.dataset.cmsBeforeBusy=button.disabled?'1':'0'",segment)
        self.assertIn("button.disabled=button.dataset.cmsBeforeBusy==='1'",segment)
        self.assertIn("delete button.dataset.cmsBeforeBusy",segment)

    def test_publish_conflicts_and_errors_keep_visible_recovery_controls(self):
        for expected in (
            "function showTransitionFeedback(error,action,applied=false)",
            "function transitionErrorInfo(error,action,applied=false)",
            "error.status===409",
            "error.status===422",
            "error.status===401",
            "error.status===403",
            "data-review-reload",
            "cms-transition-feedback",
            "请重新读取服务器状态",
            "if(applied)return {title:'操作已提交，但页面刷新失败'",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected,self.js)
        self.assertIn(".cms-transition-feedback:not([hidden])",self.css)
        self.assertIn("role=\"alert\" aria-live=\"assertive\"",self.js)

    def test_success_is_not_reported_before_record_refresh(self):
        segment=self.js[self.js.index("async function transition(action){"):
                        self.js.index("async function restoreRevision(",self.js.index("async function transition(action){"))]
        self.assertLess(segment.index("await api('/api/admin/content/"),
                        segment.index("applied=true"))
        self.assertLess(segment.index("await selectItem(item.slug)"),
                        segment.index("message({submit:"))
        self.assertIn("showTransitionFeedback(e,action,applied)",segment)
        self.assertIn("finally{btnDisable(false)}",segment)

    def test_short_rejection_reason_has_persistent_guidance(self):
        segment=self.js[self.js.index("async function transition(action){"):
                        self.js.index("async function restoreRevision(",self.js.index("async function transition(action){"))]
        self.assertIn("退回原因至少 4 个字符",segment)
        self.assertIn("showTransitionFeedback(error,action)",segment)
        self.assertIn("退回意见还不够明确",self.js)

    def test_browser_regressions_cover_actual_409_422_rejection_and_dossier_layout(self):
        for expected in (
            "V52.8 preview mirrors public research layout and website metadata",
            "V52.8 publish 422 error persists and supports safe server refresh",
            "V52.8 stale review revision 409 fails closed",
            "V52.8 rejection requires a reason",
            "forcedErrors",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected,self.browser)

    def test_cache_version_matches_the_new_editor(self):
        self.assertIn("cms.js?v=5310",self.html)
        self.assertIn("cms.css?v=5310",self.html)


if __name__=="__main__":
    unittest.main()
