"""V54.2 visual consistency and screenshot fallback contracts."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class Cms542(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Repository tests read frontend/, while the deploy image places these files
        # under static/assets and static/ respectively.
        is_source=(ROOT/'frontend/cms.js').is_file()
        asset_dir=ROOT/'frontend' if is_source else ROOT/'static/assets'
        html_path=ROOT/'frontend/cms.html' if is_source else ROOT/'static/cms.html'
        cls.js=(asset_dir/'cms.js').read_text(encoding='utf-8')
        cls.css=(asset_dir/'cms.css').read_text(encoding='utf-8')
        cls.html=html_path.read_text(encoding='utf-8')

    def test_missing_cover_is_safe(self):
        self.assertIn("thumb.classList.add('cms-thumb-missing')",self.js)
        self.assertIn("thumb.innerHTML=icon(kinds[state.kind].icon)",self.js)

    def test_screenshot_fit_and_review_modal(self):
        self.assertIn('object-fit:contain',self.css)
        self.assertIn('#cms-review-dialog.cms-v530-dialog',self.css)
        self.assertIn('max-height:calc(100dvh - 24px)',self.css)

    def test_assets(self):
        self.assertIn('/assets/cms.js?v=5701',self.html)
        self.assertIn('/assets/cms.css?v=5701',self.html)

    def test_bulk_selection_is_action_and_role_aware(self):
        self.assertIn("const bulkActionRules=",self.js)
        self.assertIn("function bulkEligibility(",self.js)
        self.assertIn("visibleEligible=listPage(listFiltered()).filter(x=>bulkEligibility(x).ok)",self.js)
        self.assertIn("items.some(x=>!bulkEligibility(x,action).ok)",self.js)
        self.assertIn("state.selectedSlugs.size>=20",self.js)
        self.assertIn('id="cms-bulk-clear"',self.html)
        self.assertIn('id="cms-bulk-help"',self.html)
        self.assertIn('选择本页符合条件的内容（最多 20 条）',self.html)

    def test_list_pager_and_sorting_contracts(self):
        self.assertIn("page:1,pageSize:24,sort:'recent'",self.js)
        self.assertIn("function listPage(filtered=listFiltered())",self.js)
        self.assertIn("state.page=page;state.selectedSlugs.clear();",self.js)
        self.assertIn("listPage(listFiltered()).filter(item=>bulkEligibility(item).ok)",self.js)
        self.assertIn('id="cms-list-pager"',self.html)
        self.assertIn('id="cms-sort"',self.html)
        self.assertIn('id="cms-page-prev"',self.html)
        self.assertIn('id="cms-page-next"',self.html)

    def test_review_queue_is_integrated_and_role_guarded(self):
        self.assertIn('id="cms-review-filter"',self.html)
        self.assertIn('data-review-compare=',self.js)
        self.assertIn("can('review')&&item.status==='review'",self.js)
        self.assertIn('function nextReviewSlug(currentSlug)',self.js)
        self.assertIn('function reviewNavigation(item)',self.js)
        self.assertIn('data-v555-next-review=',self.js)
        self.assertIn("if(!can('review')||state.busy)return;",self.js)
        self.assertIn('data-v555-review-queue',self.js)

    def test_scheduling_integrates_review_and_calendar(self):
        self.assertIn('data-schedule-open',self.js)
        self.assertIn('data-schedule-calendar',self.js)
        self.assertIn('function focusReviewSchedule()',self.js)
        self.assertIn('function openItemCalendar()',self.js)
        self.assertIn('function paintScheduleSummary()',self.js)
        self.assertIn('id="cms-v556-schedule-summary"',self.html)
        self.assertIn('<option value="attention">',self.html)
        self.assertIn("function scheduleIssue(item,now=Date.now())",self.js)
        self.assertIn("formatScheduleTime(schedule.publish_at)",self.js)

    def test_schedule_intervention_and_media_alt_shortcuts(self):
        self.assertIn("function scheduleIssue(item,now=Date.now())",self.js)
        self.assertIn('data-v557-schedule-resolve',self.js)
        self.assertIn("state.selected.status==='review'",self.js)
        self.assertIn("setEditorTab(state.selected.status==='draft'?",self.js)
        self.assertIn('id="cms-v557-schedule-alert"',self.html)
        self.assertIn("function paintScheduleSummary()",self.js)
        self.assertIn("未来 24 小时内有",self.js)
        self.assertIn('id="cms-v557-media-audit"',self.html)
        self.assertIn('id="cms-v557-show-missing"',self.html)
        self.assertIn("data-v557-edit-alt",self.js)
        self.assertIn("audit.hidden=Boolean(state.mediaField||state.mediaTarget)",self.js)

    def test_bulk_alt_and_media_reference_workbench(self):
        self.assertIn('id="cms-v558-bulk-alt-panel"',self.html)
        self.assertIn('id="cms-v558-bulk-alt-open"',self.html)
        self.assertIn('id="cms-v558-alt-save"',self.html)
        self.assertIn("function openBulkAltEditor()",self.js)
        self.assertIn("function saveBulkAlt()",self.js)
        self.assertIn("api('/api/admin/media/bulk-alt'",self.js)
        self.assertIn("data-v558-open-refs",self.js)
        self.assertIn("当前引用（CMS 草稿与已发布内容）",self.js)
        self.assertIn("mediaWorkbench.seo==='missing'",self.js)

    def test_beginner_list_filters_and_recoverable_load_failures(self):
        self.assertIn('id="cms-v559-filter-context"',self.html)
        self.assertIn('id="cms-v559-load-failure"',self.html)
        self.assertIn("function renderListContext(filtered)",self.js)
        self.assertIn("function renderListFailure(error,slug='')",self.js)
        self.assertIn("function clearListFailure()",self.js)
        self.assertIn("data-v559-retry-load",self.js)
        self.assertIn("data-v559-create-first",self.js)
        self.assertIn("state.items=[];state.selected=null;state.selectedSlugs.clear()",self.js)
        self.assertIn("state.selected=null;setStudioMode(false);drawItems()",self.js)
        self.assertIn("clearListFailure();",self.js)

if __name__=='__main__':
    unittest.main()
