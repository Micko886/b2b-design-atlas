"""V64: published resources have stable, crawlable directory routes."""
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import seo_routes,seo_directory


class DirectoryV64(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"index.html").write_text(
            '<html><head><title>Initial</title><meta name="description" content="default">'
            '<script src="/assets/app.js?v=seo-geo-v62-1" defer></script></head>'
            '<body><main id="app"><div class="shell loading">正在加载设计资源…</div></main></body></html>',
            encoding="utf-8")
        self.catalog={
            "sites":{"site-%03d"%i:{"name":"Company %03d"%i,
                     "summary":"Public research %03d"%i} for i in range(125)},
            "modules":{"hero":{"title":"Industrial Hero","lesson":"Public module"}},
            "patterns":{"evidence":{"title":"Evidence first","question":"Trust?"}},
            "articles":{"guide":{"title":"Published Article","subtitle":"Public research"}}
        }
        for key,value in (("STATIC",self.root),("catalog",lambda:self.catalog)):
            override=patch.object(seo_routes,key,value)
            override.start()
            self.addCleanup(override.stop)

    def get(self,path):
        response=seo_routes.seo_document(path)
        return response.status_code,response.body.decode(),response.headers

    def test_every_large_catalog_item_is_in_one_numbered_page(self):
        all_urls=[]
        for page,expected in ((1,60),(2,60),(3,5)):
            status,body,headers=self.get("directory/websites/"+str(page))
            self.assertEqual(status,200)
            self.assertEqual(headers["X-Robots-Tag"],"index, follow")
            self.assertNotIn('src="/assets/app.js',body)
            self.assertIn('<h1>网站案例 · 公开资源目录 · 第 '+str(page)+' 页</h1>',body)
            links=re.findall(r'<a href="(/websites/site-\d{3})">',body)
            self.assertEqual(len(links),expected)
            all_urls.extend(links)
        self.assertEqual(len(set(all_urls)),125)
        self.assertIn('rel="next" href="/directory/websites/2"',self.get("directory/websites/1")[1])
        self.assertIn('rel="prev" href="/directory/websites/2"',self.get("directory/websites/3")[1])

    def test_index_sitemap_and_canonical_are_consistent(self):
        status,home,_=self.get("directory")
        self.assertEqual(status,200)
        for kind in seo_directory.KINDS:
            self.assertIn('href="/directory/'+kind+'/1"',home)
        paths=[p for p,_ in seo_routes.sitemap_items(self.catalog)]
        self.assertEqual([p for p in paths if p.startswith("/directory/websites/")],
                         ["/directory/websites/1","/directory/websites/2","/directory/websites/3"])
        self.assertIn("/directory",paths)
        self.assertIn("/websites/site-124",paths)
        self.assertIn("/insights/guide",paths)
        detail=self.get("directory/insights/1")[1]
        self.assertIn('rel="canonical" href="'+seo_routes.ORIGIN+'/directory/insights/1"',detail)
        self.assertIn('"@type": "CollectionPage"',detail)
        self.assertIn('href="/insights/guide"',detail)
        self.assertNotIn("正在加载设计资源…",detail)

    def test_invalid_page_does_not_resolve_or_index(self):
        for path in ("directory/websites/0","directory/websites/04","directory/websites/4",
                     "directory/websites/9999","directory/unknown/1","directory/sections/no"):
            with self.subTest(path=path):
                status,body,headers=self.get(path)
                self.assertEqual(status,404)
                self.assertEqual(headers["X-Robots-Tag"],"noindex")
                self.assertNotIn('rel="canonical"',body)

    def test_catalog_changes_do_not_expose_unpublished_content(self):
        # Published-only caller contract; an item removed from that view
        # must vanish from both HTML and sitemap without redeploy.
        self.catalog["sites"].pop("site-124")
        status,body,_=self.get("directory/websites/3")
        self.assertEqual(status,200)
        self.assertNotIn("/websites/site-124",body)
        self.assertEqual(len(re.findall(r'<a href="/websites/site-\d{3}">',body)),4)
        self.assertNotIn("/websites/site-124",[p for p,_ in seo_routes.sitemap_items(self.catalog)])


if __name__=="__main__":
    unittest.main()
