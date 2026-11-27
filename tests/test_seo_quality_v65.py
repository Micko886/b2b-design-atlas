"""V65: duplicate title/description and broken-source checks in existing CMS SEO UI."""
import copy
import unittest
from app import cms_quality,seo_routes


class SeoQualityV65(unittest.TestCase):
    def setUp(self):
        self.c={
            "sites":{
                "first":{"name":"Industrial robotics manufacturing reference",
                         "summary":"A verified original website source for manufacturing product research and buyer decision evidence.",
                         "url":"https://a.example"},
                "second":{"name":" INDUSTRIAL  ROBOTICS MANUFACTURING REFERENCE ",
                          "summary":"A verified original website source for manufacturing product research and buyer decision evidence.",
                          "url":"https://b.example"}
            },
            "modules":{},
            "patterns":{},
            "articles":{
                "published":{"title":"Robotics research verification and evidence",
                             "subtitle":"Research methods for industrial robotics and evidence based buyer evaluation in complex purchasing journeys.",
                             "published_at":"2026-11-25",
                             "sections":[{"title":"Research","blocks":[{"type":"paragraph","text":"Documented evidence. "*20}]}]}
            }
        }

    def test_same_kind_duplicates_appear_in_existing_audit(self):
        before=copy.deepcopy(self.c)
        report=cms_quality.audit_published("site",self.c)
        self.assertEqual(report["total"],2)
        for entry in report["items"]:
            codes={x["code"] for x in entry["issues"]}
            self.assertIn("duplicate_title",codes)
            self.assertIn("duplicate_description",codes)
        self.assertEqual(self.c,before,"Audit must be read-only")

    def test_cross_kind_similar_titles_do_not_count_as_duplicates(self):
        self.c["patterns"]["only"]={"title":self.c["sites"]["first"]["name"],"question":"Why?"}
        self.assertEqual(cms_quality.duplicate_map("pattern",self.c),{})
        self.assertEqual(cms_quality.metadata_peers("pattern","only",
                         self.c["sites"]["first"]["name"],"Unrelated",self.c),{})

    def test_draft_preview_checks_only_existing_public_peers(self):
        article=self.c["articles"]["published"]
        draft={"title":article["title"],"subtitle":article["subtitle"],"cover_site":"example",
               "sections":[{"title":"Research","blocks":[{"type":"paragraph","text":"Sample "*40}]}]}
        self.assertNotIn("duplicate_title",[x["code"] for x in cms_quality.quality_report("new",draft)["checks"]])
        checks=cms_quality.quality_report("new",draft,self.c)["checks"]
        self.assertIn("duplicate_title",[x["code"] for x in checks])
        self.assertIn("duplicate_description",[x["code"] for x in checks])
        own=cms_quality.quality_report("published",draft,self.c)["checks"]
        self.assertNotIn("duplicate_title",[x["code"] for x in own])

    def test_article_flags_bad_link_missing_depth_and_bad_dates(self):
        item=copy.deepcopy(self.c["articles"]["published"])
        item["published_at"]="2026-19-99"
        item["sections"]=[{"title":"Research","blocks":[
            {"type":"paragraph","text":"Short public abstract."},
            {"type":"link","text":"Broken source","url":"javascript:alert(1)"}]}]
        issues=cms_quality.audit_resource("article","published",item,self.c)["issues"]
        self.assertTrue({"date","depth","invalid_links"}.issubset({x["code"] for x in issues}))

    def test_research_with_valid_source_and_depth_has_no_new_warnings(self):
        item=copy.deepcopy(self.c["articles"]["published"])
        item["sections"][0]["blocks"].append(
            {"type":"link","text":"Manufacturer manual","url":"https://docs.example.org/manual"})
        codes={x["code"] for x in cms_quality.audit_resource("article","published",item,self.c)["issues"]}
        self.assertNotIn("invalid_links",codes)
        self.assertNotIn("depth",codes)
        self.assertNotIn("date",codes)


if __name__=="__main__":unittest.main()
