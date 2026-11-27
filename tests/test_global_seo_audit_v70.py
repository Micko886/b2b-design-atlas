"""V70 published-only global editorial audit and protected CMS integration."""
import copy,unittest
from unittest.mock import patch
from fastapi import FastAPI,Request,HTTPException
from app import cms_quality,seo_routes

class GlobalAuditV70(unittest.TestCase):
    def setUp(self):
        self.c={"sites":{
          "original":{"name":"Manufacturing buyer information architecture",
                      "summary":"Original source about engineering product research and industrial procurement workflow design.",
                      "url":"https://docs.example.org"},
          "broken":{"name":"Missing supplier reference","summary":"Missing original URL."}},
          "modules":{"module":{"title":"Industrial specifications","lesson":"Product evidence",
                    "site_id":"original","url":"https://docs.example.org"}},
          "patterns":{"pattern":{"title":"Verified proof","question":"Evidence",
                    "when":"Complex procurement","modules":["module"]}},
          "articles":{"study":{"title":"Industrial B2B research methods",
                  "subtitle":"Documented observations of industrial product websites and sourcing evidence.",
                  "published_at":"2026-11-25","references":[["website","original"]],
                  "sections":[{"title":"Evidence","blocks":[{"type":"paragraph",
                              "text":"Verified engineering research. "*15}]}]}}}
    def test_public_totals_and_read_only(self):
        before=copy.deepcopy(self.c)
        overview=cms_quality.audit_overview(self.c)
        for k in ("total","flagged","high","clear"):
            self.assertEqual(overview[k],sum(cms_quality.audit_published(kind,self.c)[k]
                             for kind in ("site","module","pattern","article")))
        self.assertEqual(overview["total"],5)
        self.assertEqual(self.c,before)
    def test_issue_count_not_limited_to_first_hundred(self):
        for n in range(110):
            self.c["sites"]["x-"+str(n)]={"name":"Source "+str(n),"summary":"No URL"}
        report=cms_quality.audit_published("site",self.c,limit=10)
        self.assertEqual(len(report["items"]),10)
        self.assertEqual(report["issue_counts"]["source"],111)
        full=cms_quality.audit_overview(self.c)
        self.assertEqual(next(x["count"] for x in full["top_issues"] if x["code"]=="source"),111)
    def test_invalid_http_link_and_self_citation(self):
        article=self.c["articles"]["study"]
        article["references"]=[["article","study"]]
        article["sections"][0]["blocks"].append({"type":"link","url":"https://bad.example/a<invalid>"})
        codes={i["code"] for i in cms_quality.audit_resource("article","study",article,self.c)["issues"]}
        self.assertTrue({"sources","invalid_links","broken_refs"}.issubset(codes))
    def test_invalid_website_source_with_credentials(self):
        site=self.c["sites"]["original"];site["url"]="https://user:secret@example.org"
        codes={i["code"] for i in cms_quality.audit_resource("site","original",site,self.c)["issues"]}
        self.assertIn("source",codes)
    def test_route_checks_permission_and_keeps_kind(self):
        app=FastAPI();cms_quality.register_quality_routes(app)
        endpoint=next(r.endpoint for r in app.routes if getattr(r,"path","")=="/api/admin/seo/audit")
        request=Request({"type":"http","method":"GET","path":"/api/admin/seo/audit","headers":[],"query_string":b""})
        with patch.object(cms_quality.cms_routes,"require_admin",side_effect=HTTPException(401)):
            with self.assertRaises(HTTPException):endpoint(request,kind="site")
        with patch.object(cms_quality.cms_routes,"require_admin",return_value={"user_id":"x"}) as guard:
            with patch.object(cms_quality.cms_routes.seo_routes,"catalog",return_value=self.c):
                result=endpoint(request,kind="article")
        guard.assert_called_once_with(request,permission="view")
        self.assertEqual(result["overview"]["total"],5)
        self.assertEqual(result["kind"],"article")
    def test_existing_panel_integration(self):
        html=(seo_routes.STATIC/"cms.html").read_text(encoding="utf-8")
        js=(seo_routes.STATIC/"assets"/"cms.js").read_text(encoding="utf-8")
        self.assertIn('id="cms-audit-overview"',html)
        self.assertIn('renderSeoAuditOverview(data.overview)',js)

if __name__=="__main__":unittest.main()
