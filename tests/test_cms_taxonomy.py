"""V51.5 taxonomy regression: source overrides, deletion safety, authentication."""
import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, HTTPException
from app import cms_routes


class CategoryManagementTests(unittest.TestCase):
    def test_source_categories_are_preserved(self):
        rows=cms_routes.base_article_categories()
        self.assertTrue(any(item["id"]=="methods" for item in rows))

    def test_update_label_and_add_new_category(self):
        source=[{"id":"methods","name":"设计方法","description":"原说明"}]
        overlays=[{"id":"methods","name":"方法研究","description":"更新","status":"active"},
                  {"id":"guides","name":"实践指南","description":"新建","status":"active"}]
        result=cms_routes.merge_article_categories(source,overlays)
        self.assertEqual([x["id"] for x in result],["methods","guides"])
        self.assertEqual(result[0]["name"],"方法研究")

    def test_tombstones_hide_category_from_public_catalog(self):
        source=[{"id":"methods","name":"设计方法","description":""},
                {"id":"cases","name":"案例研究","description":""}]
        result=cms_routes.merge_article_categories(source,[{"id":"cases","status":"deleted"}])
        self.assertEqual([x["id"] for x in result],["methods"])
        self.assertEqual(len(source),2,"must not mutate checked-in source data")

    def test_usage_includes_unpublished_draft_and_published_snapshot(self):
        base={"old":{"category":"methods"}}
        rows=[
           {"slug":"new","draft_json":'{"category":"guides"}',"published_json":None},
           {"slug":"another","draft_json":'{"category":"cases"}',
            "published_json":'{"category":"guides"}'},
        ]
        self.assertEqual(cms_routes.category_usage("methods",base,rows),1)
        self.assertEqual(cms_routes.category_usage("guides",base,rows),2)
        self.assertEqual(cms_routes.category_usage("unreferenced",base,rows),0)

    def test_blank_display_name_rejected(self):
        data=cms_routes.CategoryData(id="new-category",name="   ")
        with self.assertRaises(HTTPException) as error:
            cms_routes.validate_category_data(data)
        self.assertEqual(error.exception.status_code,422)

    def test_unsafe_slug_rejected(self):
        # Explicit server guard is effective even for Pydantic versions that
        # do not enforce the Field(pattern=...) keyword.
        data=cms_routes.CategoryData.construct(id="../unsafe",name="No")
        with self.assertRaises(HTTPException) as error:
            cms_routes.validate_category_data(data)
        self.assertEqual(error.exception.status_code,422)

    def test_delete_used_source_category_rejected_before_write(self):
        app=FastAPI()
        cms_routes.register_cms_routes(app)
        endpoint=next(r.endpoint for r in app.routes
                      if getattr(r,"path",None)=="/api/admin/categories/{category_id}"
                      and "DELETE" in getattr(r,"methods",set()))
        connection=MagicMock()
        connection.one.return_value=None
        connection.all.return_value=[]
        ctx=MagicMock()
        ctx.__enter__.return_value=connection
        ctx.__exit__.return_value=False
        with patch.object(cms_routes,"require_admin",return_value={"user_id":"admin"}), \
             patch.object(cms_routes,"ensure_cms"), \
             patch.object(cms_routes.user_auth,"db",return_value=ctx):
            with self.assertRaises(HTTPException) as error:
                endpoint("methods",object())
        self.assertEqual(error.exception.status_code,409)
        connection.execute.assert_not_called()

    def test_taxonomy_write_requires_admin(self):
        app=FastAPI()
        cms_routes.register_cms_routes(app)
        endpoint=next(r.endpoint for r in app.routes
                      if getattr(r,"path",None)=="/api/admin/categories"
                      and "POST" in getattr(r,"methods",set()))
        with patch.object(cms_routes,"require_admin",side_effect=HTTPException(401,"login")):
            with self.assertRaises(HTTPException) as error:
                endpoint(cms_routes.CategoryData(id="new-one",name="新分类"),object())
        self.assertEqual(error.exception.status_code,401)

if __name__=="__main__":
    unittest.main()
