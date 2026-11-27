"""V60: mobile cards, image loading, fallback and public route contracts."""
from __future__ import annotations
import re
import unittest
from pathlib import Path

from app import seo_routes


STATIC=Path(__file__).resolve().parents[1]/"static"


class MobileExperienceV60(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(STATIC/"assets"/"app.js").read_text(encoding="utf-8")
        cls.css=(STATIC/"assets"/"app.css").read_text(encoding="utf-8")
        cls.html=(STATIC/"index.html").read_text(encoding="utf-8")

    def test_waterfall_columns_follow_viewport_and_keep_natural_item_height(self):
        self.assertIn(".masonry{column-count:4;column-gap:18px}",self.css)
        self.assertIn(".masonry-compact{column-count:5}",self.css)
        self.assertIn(".masonry{column-count:2}.masonry-compact{column-count:3}",self.css)
        self.assertIn(".masonry{column-count:1}.masonry-compact{column-count:2",self.css)
        self.assertIn(".masonry-compact{column-count:1}",self.css)
        self.assertIn("break-inside:avoid",self.css)
        self.assertIn('class="masonry ${state.density',self.js)
        self.assertIn("aria-label=\"紧凑模式\"",self.js)

    def test_visible_media_loads_first_and_offscreen_research_is_lazy(self):
        self.assertIn("index<2?'loading=\"eager\"':'loading=\"lazy\"'",self.js)
        self.assertIn("index===0?'fetchpriority=\"high\"':''",self.js)
        self.assertIn('decoding="async"',self.js)
        self.assertIn('loading="lazy" decoding="async" src="${img(articleImage(a))}"',self.js)
        self.assertIn('loading="eager" fetchpriority="high" decoding="async" src="${img(articleImage(a))}"',self.js)
        self.assertIn("!category&&!q&&!p.get('topic')&&sort==='latest'?insightFeature(feature):''",self.js)

    def test_missing_previews_are_neutral_and_interactions_remain_available(self):
        self.assertIn("document.addEventListener('error',ev=>",self.js)
        self.assertIn("if(image?.tagName!=='IMG')return",self.js)
        self.assertIn("visual.classList.add('visual-load-failed')",self.js)
        self.assertIn("图片预览暂不可用",self.js)
        self.assertIn(".visual-load-failed img{display:none!important}",self.css)
        self.assertIn(".reference-media.visual-load-failed>a{display:block;min-height:",self.css)
        self.assertIn(".reference-media.visual-load-failed .card-actions{z-index:2}",self.css)
        self.assertIn("pointer-events:none",self.css.split("/* V60 ·",1)[1])
        self.assertIn("insight-topic-visual",self.js)

    def test_mobile_navigation_state_and_client_data_cache_refresh(self):
        self.assertIn("$('.mobile-menu-button')?.setAttribute('aria-expanded','false')",self.js)
        self.assertIn("if(ev.key==='Escape')",self.js)
        self.assertIn("/assets/articles.json?v=60",self.js)
        self.assertIn("app.js?v=mobile-v60-1",self.html)
        self.assertIn("app.css?v=mobile-v60-1",self.html)
        self.assertIn("function researchTopic(topic)",self.js)
        self.assertIn("topic.related.includes(a.id)",self.js)

    def test_public_internal_link_targets_resolve_to_indexable_pages(self):
        catalog=seo_routes.base_catalog()
        for route,key in (("websites","sites"),("sections","modules"),
                          ("patterns","patterns"),("insights","articles")):
            with self.subTest(route=route):
                records=list(catalog[key].items())[:5]
                self.assertTrue(records)
                for slug,record in records:
                    page=seo_routes.seo_record("/"+route+"/"+slug,catalog)
                    self.assertIsNotNone(page)
                    self.assertTrue(page["indexed"])
                    self.assertEqual(page["path"],"/"+route+"/"+slug)
                    self.assertTrue(page["title"])
                    self.assertTrue(page["description"])


if __name__=="__main__":
    unittest.main()
