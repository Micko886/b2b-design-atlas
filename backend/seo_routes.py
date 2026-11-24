"""Route-aware HTTP status and SEO for B2B Atlas' SPA.
Only public, published resources receive indexable metadata.
No user data enters HTML, sitemap or social tags.
"""
from __future__ import annotations
import html, json, os, re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

BASE = Path(__file__).resolve().parents[1]
STATIC = BASE / "static"
ORIGIN = os.getenv("ATLAS_PUBLIC_ORIGIN","https://b2b-design-atlas-preview.onrender.com").rstrip("/")
PUBLIC = {
    "":("B2B Atlas · B2B 视觉设计研究库","工业、科技与企业产品的网站、页面模块和设计模式研究库。"),
    "websites":("Websites · B2B 网站灵感库","探索真实的工业、科技与企业官网，研究配色、布局与 B2B 转化设计。"),
    "sections":("Sections · 页面模块参考","发现优秀 B2B 官网首屏、产品、案例和信任模块，研究页面设计细节。"),
    "patterns":("Patterns · 设计模式研究","从真实案例中探索可复用的 B2B 设计问题、原则和页面模式。"),
    "insights":("Insights · 资讯与研究","阅读 B2B 网站案例分析、设计方法、视觉系统和内容策略原创文章。")
}
PRIVATE = {
    "account":("个人中心","管理个人资料、收藏与研究板。"),
    "collections":("我的收藏","你保存的 B2B 设计参考资料。"),
    "discover":("我的收藏","浏览已收藏的设计资源。"),
    "board":("研究工作台","整理设计资料、个人笔记和项目研究。"),
    "login":("登录账户","登录你的 B2B Atlas 账户。"),
    "register":("创建账户","创建 B2B Atlas 账户并收藏参考资料。"),
    "forgot-password":("找回密码","通过一次性安全链接重置 B2B Atlas 账户密码。"),
    "reset-password":("重置密码","设置新的 B2B Atlas 登录密码。")
}
def read_json(path, default):
    try:return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,ValueError):return default

@lru_cache(maxsize=1)
def catalog():
    src=read_json(BASE/"app"/"source_index.json",{})
    modules=read_json(BASE/"app"/"module_catalog.json",[])
    patterns=read_json(STATIC/"assets"/"patterns.json",[])
    articles=read_json(STATIC/"assets"/"articles.json",{})
    return {
        "sites":{x["id"]:x for x in src.get("sites",[]) if x.get("id")},
        "modules":{x["id"]:x for x in modules if x.get("id")} if isinstance(modules,list) else {},
        "patterns":{x["id"]:x for x in patterns if x.get("id")} if isinstance(patterns,list) else {},
        "articles":{x["id"]:x for x in articles.get("articles",[]) if x.get("id")}
    }

def seo_record(path):
    parts=[x for x in path.strip("/").split("/") if x]
    if len(parts)==0:return {"title":PUBLIC[""][0],"description":PUBLIC[""][1],"path":"/","indexed":True}
    if len(parts)==1 and parts[0] in PUBLIC:
        k=parts[0]
        return {"title":PUBLIC[k][0],"description":PUBLIC[k][1],"path":"/"+k,"indexed":True}
    if len(parts)==1 and parts[0] in PRIVATE:
        k=parts[0]
        return {"title":PRIVATE[k][0],"description":PRIVATE[k][1],"path":"/"+k,"indexed":False}
    if len(parts)!=2:return None
    category,slug=parts
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,120}",slug):return None
    c=catalog()
    if category=="websites" and slug in c["sites"]:
        x=c["sites"][slug]
        return {"title":x.get("name",slug)+" · 网站设计研究",
                "description":x.get("summary") or x.get("focus") or "研究 "+x.get("name",slug)+" 的网站设计。",
                "path":path,"indexed":True,"image":"/screenshots/sites/"+slug+".webp"}
    if category=="sections" and slug in c["modules"]:
        x=c["modules"][slug]
        return {"title":x.get("title",slug)+" · 页面模块研究",
                "description":x.get("lesson") or x.get("summary") or "从真实 B2B 案例中研究页面结构和模块设计。",
                "path":path,"indexed":True}
    if category=="patterns" and slug in c["patterns"]:
        x=c["patterns"][slug]
        return {"title":x.get("title",slug)+" · 设计模式",
                "description":x.get("question") or x.get("principle") or "B2B 数字产品设计方法研究。",
                "path":path,"indexed":True}
    if category=="insights" and slug in c["articles"]:
        x=c["articles"][slug]
        return {"title":x.get("title",slug),
                "description":x.get("subtitle") or "B2B Atlas 原创设计研究文章",
                "path":path,"indexed":True,"kind":"article",
                "published":x.get("published_at",""),"author":x.get("author","B2B Atlas 编辑部"),
                "image":("/screenshots/sites/"+x["cover_site"]+".webp") if x.get("cover_site") in c["sites"] else None}
    return None

def safe(v,maxlen=300):
    return html.escape(str(v or "")[:maxlen],quote=True)

def seo_document(full_path):
    clean="/"+full_path.strip("/") if full_path.strip("/") else "/"
    record=seo_record(clean)
    found=record is not None
    if not found:record={"title":"404 · 页面未找到","description":"页面不存在或已移动。探索 B2B Atlas 的网站、页面模块和设计文章。","path":clean,"indexed":False}
    canonical=ORIGIN+record["path"]
    title=record["title"]+" · B2B Atlas"
    desc=record["description"]
    template=(STATIC/"index.html").read_text(encoding="utf-8")
    template=re.sub(r"<title>.*?</title>","<title>"+safe(title,220)+"</title>",template,count=1,flags=re.S)
    template=re.sub(r'<meta name="description" content="[^"]*">','<meta name="description" content="'+safe(desc,270)+'">',template,count=1)
    image=ORIGIN+(record.get("image") or "/screenshots/sites/vast.webp")
    extras=(
        '<link rel="canonical" href="'+safe(canonical,650)+'">'
        '<meta name="robots" content="'+("index, follow" if record["indexed"] else "noindex, follow")+'">'
        '<meta property="og:type" content="'+("article" if record.get("kind")=="article" else "website")+'">'
        '<meta property="og:site_name" content="B2B Atlas">'
        '<meta property="og:title" content="'+safe(title,220)+'">'
        '<meta property="og:description" content="'+safe(desc,270)+'">'
        '<meta property="og:url" content="'+safe(canonical,650)+'">'
        '<meta property="og:image" content="'+safe(image,650)+'">'
        '<meta name="twitter:card" content="summary_large_image">'
    )
    if record.get("kind")=="article":
        data={"@context":"https://schema.org","@type":"Article","headline":record["title"],
              "description":desc,"datePublished":record.get("published"),
              "author":{"@type":"Organization","name":record.get("author","B2B Atlas")},
              "publisher":{"@type":"Organization","name":"B2B Atlas"},"mainEntityOfPage":canonical,"image":image}
        extras+='<script type="application/ld+json">'+json.dumps(data,ensure_ascii=False).replace("<","\\u003c")+'</script>'
    template=template.replace("</head>",extras+"</head>",1)
    headers={"Cache-Control":"no-cache","X-Robots-Tag":"noindex" if not record["indexed"] else "index, follow"}
    return HTMLResponse(template,status_code=200 if found else 404,headers=headers)

def register_seo_routes(app:FastAPI):
    @app.get("/robots.txt",include_in_schema=False)
    def robots():
        return PlainTextResponse("User-agent: *\nDisallow: /account\nDisallow: /collections\nDisallow: /board\nDisallow: /login\nDisallow: /register\nSitemap: "+ORIGIN+"/sitemap.xml\n",headers={"Cache-Control":"public, max-age=3600"})
    @app.get("/sitemap.xml",include_in_schema=False)
    def sitemap():
        c=catalog()
        paths=["/","/websites","/sections","/patterns","/insights"]
        paths+=["/websites/"+x for x in sorted(c["sites"])]
        paths+=["/sections/"+x for x in sorted(c["modules"])]
        paths+=["/patterns/"+x for x in sorted(c["patterns"])]
        paths+=["/insights/"+x for x in sorted(c["articles"])]
        body='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+safe(ORIGIN+x,700)+'</loc></url>' for x in paths)+'</urlset>'
        return Response(body,media_type="application/xml",headers={"Cache-Control":"public, max-age=3600"})
    @app.middleware("http")
    async def security_headers(request,call_next):
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"]="DENY"
        response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
        if request.url.scheme=="https" or request.headers.get("x-forwarded-proto")=="https":
            response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
        return response
