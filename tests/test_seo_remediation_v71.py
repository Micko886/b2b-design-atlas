"""V71: publication-only remediation checks and CMS workflow integration."""
import unittest
from unittest.mock import patch
from fastapi import FastAPI,Request,HTTPException
from app import cms_quality,seo_routes

class RemediationV71(unittest.TestCase):
    def setUp(self):
        self.c={"sites":{
          "source":{"name":"Industrial original reference","summary":"Documented original research source.","url":"https://source.example.org"},
          "missing":{"name":"Site needing repair","summary":"Site description"}
        },"modules":{},"patterns":{},"articles":{}}
        app=FastAPI();cms_quality.register_quality_routes(app)
        self.endpoint=next(r.endpoint for r in app.routes if r.path=="/api/admin/seo/audit/item")
        self.request=Request({"type":"http","method":"GET","path":"/api/admin/seo/audit/item",
                              "headers":[],"query_string":b""})
    def test_permission_is_checked_before_public_catalog_read(self):
        with patch.object(cms_quality.cms_routes,"require_admin",side_effect=HTTPException(401)):
            with patch.object(cms_quality.cms_routes.seo_routes,"catalog") as source:
                with self.assertRaises(HTTPException):self.endpoint(self.request,"site","source")
                source.assert_not_called()
    def test_individual_remediation_is_not_limited_to_top_100(self):
        for i in range(120):
            self.c["sites"]["case-"+str(i)]={"name":"A case "+str(i),"summary":"Missing URL"}
        with patch.object(cms_quality.cms_routes,"require_admin",return_value={}):
            with patch.object(cms_quality.cms_routes.seo_routes,"catalog",return_value=self.c):
                data=self.endpoint(self.request,"site","case-119")
        self.assertTrue(data["published"])
        self.assertIn("source",{x["code"] for x in data["issues"]})
    def test_verification_changes_only_when_public_catalog_changes(self):
        with patch.object(cms_quality.cms_routes,"require_admin",return_value={}):
            with patch.object(cms_quality.cms_routes.seo_routes,"catalog",return_value=self.c):
                original=self.endpoint(self.request,"site","missing")
                self.c["sites"]["missing"]["url"]="https://supplier.example.org"
                current=self.endpoint(self.request,"site","missing")
                self.c["sites"].pop("missing")
                with self.assertRaises(HTTPException) as error:
                    self.endpoint(self.request,"site","missing")
        self.assertIn("source",{x["code"] for x in original["issues"]})
        self.assertNotIn("source",{x["code"] for x in current["issues"]})
        self.assertEqual(error.exception.status_code,404)
    def test_invalid_slug_cannot_be_read(self):
        with patch.object(cms_quality.cms_routes,"require_admin",return_value={}):
            with patch.object(cms_quality.cms_routes.seo_routes,"catalog") as source:
                with self.assertRaises(HTTPException) as error:
                    self.endpoint(self.request,"site","../private")
                self.assertEqual(error.exception.status_code,422)
                source.assert_not_called()
    def test_existing_editor_has_explicit_publish_then_verify_contract(self):
        js=(seo_routes.STATIC/"assets"/"cms.js").read_text(encoding="utf-8")
        html=(seo_routes.STATIC/"cms.html").read_text(encoding="utf-8")
        self.assertIn("verifySeoPublished()",js)
        self.assertIn("stage:'editing'",js)
        self.assertIn("seoAuditTarget.stage='draft'",js)
        self.assertIn("data-seo-audit-verify",js)
        self.assertIn("data-seo-audit-return",js)
        self.assertIn('id="cms-audit-followup"',html)
        self.assertIn('/assets/cms.js?v=7301',html)
        self.assertIn('/assets/cms.css?v=7301',html)

if __name__=="__main__":
    unittest.main()
