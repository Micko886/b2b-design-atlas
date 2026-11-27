"""V59 readability, accessible mobile anchors and crawler tables."""
from __future__ import annotations
import re
import json
import unittest
from pathlib import Path

from app import seo_routes

STATIC=Path(__file__).resolve().parents[1]/"static"


class ReadingContractsV59(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(STATIC/"assets"/"app.js").read_text(encoding="utf-8")
        cls.css=(STATIC/"assets"/"app.css").read_text(encoding="utf-8")
        articles=json.loads((STATIC/"assets"/"articles.json").read_text(encoding="utf-8"))["articles"]
        cls.topics=[article for article in articles if article.get("industry_topic")]

    def test_mobile_toc_appears_before_article_body_and_has_real_section_links(self):
        self.assertIn("function articleMobileToc(a)",self.js)
        self.assertIn('class="insight-mobile-toc"',self.js)
        self.assertIn('aria-label="手机端文章章节目录"',self.js)
        self.assertIn('data-action="anchor"',self.js)
        self.assertIn('articleMobileToc(a)}<div class="insight-intro">',self.js)
        self.assertIn('tabindex="-1"',self.js)
        self.assertIn(".insight-mobile-toc{display:none}",self.css)
        css_mobile=self.css.split("/* V59 ·",1)[-1]
        self.assertIn("@media(max-width:680px)",css_mobile)
        self.assertIn(".insight-mobile-toc{display:block",css_mobile)
        self.assertIn(".insight-mobile-toc summary:focus-visible",css_mobile)

    def test_deep_link_navigation_is_keyboard_and_reduced_motion_aware(self):
        self.assertIn("function scrollToCurrentHash()",self.js)
        self.assertIn("history.replaceState(history.state",self.js)
        self.assertIn("requestAnimationFrame(scrollToCurrentHash)",self.js)
        self.assertIn("target.closest('.insight-mobile-toc')",self.js)
        self.assertIn("section.focus({preventScroll:true})",self.js)
        self.assertIn("(prefers-reduced-motion: reduce)",self.js)

    def test_research_tables_have_meaningful_headers_and_scroll_region(self):
        self.assertIn("function renderResearchTable(block)",self.js)
        self.assertIn('role="region" tabindex="0"',self.js)
        self.assertIn('<th scope="col">',self.js)
        self.assertIn("if(type==='table')return renderResearchTable(block)",self.js)
        self.assertIn(".insight-block-table-scroll:focus-visible",self.css)
        self.assertIn("overscroll-behavior-inline:contain",self.css)
        self.assertEqual(len(self.topics),3)
        self.assertTrue(all(any(block.get("type")=="table"
            for sec in article["sections"] for block in sec["blocks"])
            for article in self.topics))

    def test_crawler_table_escapes_content_and_retains_semantics(self):
        body=seo_routes._research_table([
            ["工艺", "说明", "限制"],
            ["CNC", "<script>alert('x')</script>", "需要核实"],
            ["钣金", "安全内容", "参考来源"],
        ])
        self.assertIn('<th scope="col">工艺</th>',body)
        self.assertIn('<th scope="col">说明</th>',body)
        self.assertIn("<tbody>",body)
        self.assertIn("<td>CNC</td>",body)
        self.assertIn("&lt;script&gt;",body)
        self.assertNotIn("<script>",body)
        self.assertEqual(seo_routes._research_table([]),"")
        catalog=seo_routes.base_catalog()
        for article in self.topics:
            with self.subTest(article=article["id"]):
                route="insights/"+article["id"]
                record=seo_routes.seo_record(route,catalog)
                prerender=seo_routes.public_prerender(route,record,catalog)
                self.assertIn('<th scope="col">',prerender)
                self.assertIn('aria-label="研究对比表格"',prerender)
                self.assertIn('<a rel="nofollow noopener noreferrer"',prerender)

    def test_research_topic_css_uses_only_defined_color_tokens(self):
        root=self.css.split("\n",3)[1]
        definitions=set(re.findall(r"(--[a-z0-9-]+)\s*:",root))
        self.assertTrue({"--paper","--soft","--ink","--muted","--blue"}.issubset(definitions))
        section=self.css.split("/* V58 ·",1)[-1].split("/* V59 ·",1)[0]
        uses=set(re.findall(r"var\((--[a-z0-9-]+)\)",section))
        self.assertTrue(uses<=definitions,"Undefined topic color tokens: "+str(uses-definitions))
        for obsolete in ("--surface","--surface-2","--muted-strong","--ink-strong"):
            self.assertNotIn("var("+obsolete+")",section)
        self.assertIn(".insight-topic-card:focus-visible",section)


if __name__=="__main__":
    unittest.main()
