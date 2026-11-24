"""Exercise exact HTTP SEO response, sitemap and error statuses without production."""
import tempfile, json
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
import seo_routes as seo

with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    (root/"app").mkdir()
    (root/"static"/"assets").mkdir(parents=True)
    (root/"static"/"index.html").write_text('<html><head><title>Default</title><meta name="description" content="old"></head><body><main>Loading</main></body></html>')
    (root/"app"/"source_index.json").write_text(json.dumps({"sites":[{"id":"vast","name":"Vast","summary":"Space station engineering"}]}))
    (root/"app"/"module_catalog.json").write_text(json.dumps([{"id":"vast-hero","title":"Orbital Hero","summary":"Hero study"}]))
    (root/"static"/"assets"/"patterns.json").write_text(json.dumps([{"id":"object-first-hero","title":"Object first","question":"Why product hero?"}]))
    (root/"static"/"assets"/"articles.json").write_text(json.dumps({"articles":[{"id":"good-study","title":"B2B Research","subtitle":"Design method","published_at":"2026-11-24","cover_site":"vast"}]}))
    seo.BASE=root;seo.STATIC=root/"static";seo.catalog.cache_clear()
    for path,status,expected in [
        ("/",200,"B2B Atlas"),("/websites",200,"Websites"),("/websites/vast",200,"Space station"),
        ("/sections/vast-hero",200,"Orbital Hero"),("/patterns/object-first-hero",200,"Object first"),
        ("/insights/good-study",200,"Article"),("/account",200,"noindex"),
        ("/forgot-password",200,"noindex"),("/compare",200,"noindex"),("/websites/unknown",404,"noindex"),
        ("/insights/unknown",404,"404"),("/account/invalid",404,"noindex"),("/missing",404,"404")]:
        response=seo.seo_document(path.lstrip("/"))
        assert response.status_code==status,(path,response.status_code)
        assert expected in response.body.decode("utf-8"),(path,expected)
    home=seo.seo_document("websites/vast").body.decode("utf-8")
    assert '<link rel="canonical" href="https://b2b-design-atlas-preview.onrender.com/websites/vast">' in home
    assert '<meta property="og:title" content="Vast' in home
    article=seo.seo_document("insights/good-study").body.decode("utf-8")
    assert 'id="atlas-seo-schema"' in article
    app=FastAPI()
    seo.register_seo_routes(app)
    client=TestClient(app,base_url="https://testserver")
    sitemap=client.get("/sitemap.xml")
    assert sitemap.status_code==200
    assert "/websites/vast" in sitemap.text and "/insights/good-study" in sitemap.text
    assert "/account" not in sitemap.text
    robots=client.get("/robots.txt")
    assert "Disallow: /account" in robots.text
    assert robots.headers["x-content-type-options"]=="nosniff"
    assert robots.headers["x-frame-options"]=="DENY"
print("SEO_V42_QA_PASS: exact HTTP 404, dynamic SEO, canonical, sitemap, robots, secure headers")
