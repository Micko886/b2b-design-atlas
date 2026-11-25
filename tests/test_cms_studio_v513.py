"""V51.13 CMS: managed tags, safe review rejection and revision guards."""
import unittest
from unittest.mock import MagicMock,patch
from fastapi import FastAPI,HTTPException
from app import cms_routes


class CMSStudioV513Tests(unittest.TestCase):
    def base(self):
        return {"a":{"tags":["UX","Color"]},"b":{"tags":["UX"]}}

    def rows(self):
        return [
            {"slug":"draft-one","draft_json":'{"tags":["UX","Hero"]}',"published_json":None},
            {"slug":"draft-two","draft_json":'{"tags":["Hero"]}',"published_json":'{"tags":["Color"]}'}
        ]

    def test_tag_directory_merges_content_and_manually_curated(self):
        result=cms_routes.merge_editorial_tags(
            self.base(),self.rows(),[
                {"name":"Hero","description":"首屏结构","status":"active"},
                {"name":"New","description":"新加标签","status":"active"},
                {"name":"Deleted","description":"","status":"deleted"}
            ])
        by_name={x["name"]:x for x in result}
        self.assertEqual(by_name["UX"]["usage"],3)
        self.assertEqual(by_name["Hero"]["usage"],2)
        self.assertEqual(by_name["Color"]["usage"],2)
        self.assertEqual(by_name["New"]["usage"],0)
        self.assertNotIn("Deleted",by_name)
        self.assertEqual(by_name["Hero"]["description"],"首屏结构")

    def test_tag_usage_deduplicates_same_article_across_snapshots(self):
        self.assertEqual(cms_routes.article_tag_usage("Color",self.base(),self.rows()),2)
        self.assertEqual(cms_routes.article_tag_usage("uX",self.base(),self.rows()),3)

    def test_tag_names_reject_markup_or_control_characters(self):
        for name in ("  ","<script>","UX\nprivate","x"*33):
            with self.subTest(name=name):
                self.assertFalse(cms_routes.normalize_editorial_tag(name))
        self.assertEqual(cms_routes.normalize_editorial_tag("  UX Research  "),"UX Research")

    def test_tag_validation_rejects_blank_and_html(self):
        for name in ("  ","<script>"):
            with self.subTest(name=name),self.assertRaises(HTTPException) as issue:
                cms_routes.validate_tag_data(cms_routes.TagData(name=name))
            self.assertEqual(issue.exception.status_code,422)

    def test_review_reason_needs_explanation(self):
        for reason in ("","a","   "):
            with self.subTest(reason=reason),self.assertRaises(HTTPException):
                cms_routes.validate_review_reason(reason)
        self.assertIsNone(cms_routes.validate_review_reason("摘要需要补充来源"))

    def test_reject_endpoint_requires_auth(self):
        app=FastAPI()
        cms_routes.register_cms_routes(app)
        endpoint=next(r.endpoint for r in app.routes
                      if getattr(r,"path",None)=="/api/admin/content/{kind}/{slug}/reject")
        with patch.object(cms_routes,"require_admin",side_effect=HTTPException(401,"login")):
            with self.assertRaises(HTTPException) as error:
                endpoint("article","demo",cms_routes.RejectDecision(
                    expected_revision=2,reason="需要补充资料"),object())
        self.assertEqual(error.exception.status_code,401)

    def mock_db(self,status="review"):
        db=MagicMock()
        db.one.return_value={
            "status":status,"revision":2,"draft_json":'{"title":"Draft"}',
            "published_json":'{"title":"Live"}',"published_at":"2026-11-24",
            "published_by":"u1"
        }
        db.execute.return_value.rowcount=1
        ctx=MagicMock()
        ctx.__enter__.return_value=db
        ctx.__exit__.return_value=False
        return db,ctx

    def test_reject_draft_is_blocked_without_write(self):
        app=FastAPI();cms_routes.register_cms_routes(app)
        endpoint=next(r.endpoint for r in app.routes
                      if getattr(r,"path",None)=="/api/admin/content/{kind}/{slug}/reject")
        db,ctx=self.mock_db("draft")
        with patch.object(cms_routes,"require_admin",return_value={"user_id":"u1"}),\
             patch.object(cms_routes,"ensure_cms"),\
             patch.object(cms_routes.user_auth,"db",return_value=ctx):
            with self.assertRaises(HTTPException) as err:
                endpoint("article","demo",cms_routes.RejectDecision(
                    expected_revision=2,reason="需要补充信息"),object())
        self.assertEqual(err.exception.status_code,409)
        db.execute.assert_not_called()

    def test_valid_rejection_returns_to_draft_and_keeps_public_snapshot(self):
        app=FastAPI();cms_routes.register_cms_routes(app)
        endpoint=next(r.endpoint for r in app.routes
                      if getattr(r,"path",None)=="/api/admin/content/{kind}/{slug}/reject")
        db,ctx=self.mock_db("review")
        with patch.object(cms_routes,"require_admin",return_value={"user_id":"u1"}),\
             patch.object(cms_routes,"ensure_cms"),\
             patch.object(cms_routes,"invalidate"),\
             patch.object(cms_routes.user_auth,"db",return_value=ctx):
            result=endpoint("article","demo",cms_routes.RejectDecision(
                expected_revision=2,reason="请补充图片来源说明"),object())
        self.assertEqual(result["status"],"draft")
        self.assertEqual(result["revision"],3)
        sql=[call.args[0] for call in db.execute.call_args_list]
        self.assertTrue(any("atlas_cms_review_notes" in query for query in sql))
        self.assertIn("SET status=?",sql[0])
        self.assertEqual(db.execute.call_args_list[0].args[1][0],"draft")
        self.assertIn('{"title":"Live"}',db.execute.call_args_list[0].args[1])

    def test_registered_tag_routes_have_expected_methods(self):
        app=FastAPI();cms_routes.register_cms_routes(app)
        paths={(route.path,method) for route in app.routes
               for method in (getattr(route,"methods",set()) or set())}
        for path,method in [
            ("/api/admin/tags","GET"),("/api/admin/tags","POST"),
            ("/api/admin/tags/{tag_name}","PUT"),
            ("/api/admin/tags/{tag_name}","DELETE"),
            ("/api/admin/content/{kind}/{slug}/reject","POST")
        ]:
            self.assertIn((path,method),paths)


if __name__=="__main__":
    unittest.main()
