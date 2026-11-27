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
    "reset-password":("重置密码","设置新的 B2B Atlas 登录密码。"),
    "compare":("网站对比","登录后可保存和管理你的网站横向对比研究。")
}
def read_json(path, default):
    try:return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,ValueError):return default

def _snapshot_if_present(item,folder):
    """Fill legacy missing preview fields using actual, shipped screenshot files.

    Only repository-backed records are touched. Do not fabricate images for
    new CMS entries or overwrite existing approved screenshot choices.
    """
    if not isinstance(item,dict):return item
    current=item.get("screenshot_url")
    if isinstance(current,str) and current.strip():
        return item
    slug=item.get("id")
    if not isinstance(slug,str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,110}",slug):
        return item
    candidate=f"/screenshots/{folder}/{slug}.webp"
    if (BASE/candidate.lstrip("/")).is_file():
        return {**item,"screenshot_url":candidate}
    return item


@lru_cache(maxsize=1)
def base_catalog():
    src=read_json(BASE/"app"/"source_index.json",{})
    modules=read_json(BASE/"app"/"module_catalog.json",[])
    patterns=read_json(STATIC/"assets"/"patterns.json",[])
    articles=read_json(STATIC/"assets"/"articles.json",{})
    return {
        "sites":{x["id"]:_snapshot_if_present(x,"sites") for x in src.get("sites",[]) if x.get("id")},
        "modules":{x["id"]:_snapshot_if_present(x,"modules") for x in modules if x.get("id")} if isinstance(modules,list) else {},
        "patterns":{x["id"]:x for x in patterns if x.get("id")} if isinstance(patterns,list) else {},
        "articles":{x["id"]:x for x in articles.get("articles",[]) if x.get("id")}
    }

def catalog():
    # Keep original source files cached, apply only *published* CMS snapshots.
    # Drafts, submitted reviews and audit records never reach public views.
    base=base_catalog()
    try:
        from app.cms_routes import merge_catalog
    except ImportError:
        return base
    return merge_catalog(base)
catalog.cache_clear=base_catalog.cache_clear

def read_page_seo():
    # The public HTML and browser navigation must use approved snapshots only.
    try:
        from app.seo_pages import published_pages
        return published_pages()
    except Exception:
        return {}


def seo_record(path,collection=None,page_overrides=None):
    parts=[x for x in path.strip("/").split("/") if x]
    if not parts or (len(parts)==1 and parts[0] in PUBLIC):
        k=parts[0] if parts else ""
        page="home" if not parts else k
        cfg=(page_overrides if page_overrides is not None else read_page_seo()).get(page,{})
        return {"title":cfg.get("seo_title") or PUBLIC[k][0],
                "description":cfg.get("seo_description") or PUBLIC[k][1],
                "image":public_image(cfg.get("seo_image")),
                "keywords":cfg.get("seo_keywords") or "",
                "path":"/"+k if k else "/","indexed":True}
    if len(parts)==1 and parts[0] in PRIVATE:
        k=parts[0]
        return {"title":PRIVATE[k][0],"description":PRIVATE[k][1],"path":"/"+k,"indexed":False}
    if len(parts)!=2:return None
    category,slug=parts
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,120}",slug):return None
    c=collection if collection is not None else catalog()
    if category=="websites" and slug in c["sites"]:
        x=c["sites"][slug]
        return {"title":x.get("seo_title") or x.get("name",slug)+" · 网站设计研究",
                "description":x.get("seo_description") or x.get("summary") or x.get("focus") or "研究 "+x.get("name",slug)+" 的网站设计。",
                "path":path,"indexed":True,"image":resource_image(category,x,c),
                "keywords":x.get("seo_keywords") or ""}
    if category=="sections" and slug in c["modules"]:
        x=c["modules"][slug]
        return {"title":x.get("seo_title") or x.get("title",slug)+" · 页面模块研究",
                "description":x.get("seo_description") or x.get("lesson") or x.get("summary") or "从真实 B2B 案例中研究页面结构和模块设计。",
                "path":path,"indexed":True,"image":resource_image(category,x,c),
                "keywords":x.get("seo_keywords") or ""}
    if category=="patterns" and slug in c["patterns"]:
        x=c["patterns"][slug]
        return {"title":x.get("seo_title") or x.get("title",slug)+" · 设计模式",
                "description":x.get("seo_description") or x.get("question") or x.get("principle") or "B2B 数字产品设计方法研究。",
                "path":path,"indexed":True,"image":resource_image(category,x,c),
                "keywords":x.get("seo_keywords") or ""}
    if category=="insights" and slug in c["articles"]:
        x=c["articles"][slug]
        return {"title":x.get("seo_title") or x.get("title",slug),
                "description":x.get("seo_description") or x.get("subtitle") or "B2B Atlas 原创设计研究文章",
                "path":path,"indexed":True,"kind":"article",
                "published":x.get("published_at",""),"author":x.get("author","B2B Atlas 编辑部"),
                "image":resource_image(category,x,c),
                "keywords":x.get("seo_keywords") or ", ".join(t for t in x.get("tags",[]) if isinstance(t,str)) if isinstance(x.get("tags"),list) else x.get("seo_keywords") or ""}
    return None

def safe(v,maxlen=300):
    return html.escape(str(v or "")[:maxlen],quote=True)


_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,120}")
_MEDIA_IMAGE = re.compile(r"/api/media/[0-9a-f-]{36}")
_SHOT_IMAGE = re.compile(r"/screenshots/(?:sites|modules)/[a-z0-9][a-z0-9/_-]*\.(?:webp|png|jpe?g)",re.I)


def public_image(value):
    """Only known local public image paths can enter metadata or HTML."""
    if isinstance(value,str) and (_MEDIA_IMAGE.fullmatch(value) or _SHOT_IMAGE.fullmatch(value)):
        return value
    return None


def resource_image(kind, item, collection):
    """Use the editor's sharing override only for social and structured metadata."""
    return public_image(item.get("seo_image")) or content_image(kind,item,collection)


def content_image(kind,item,collection):
    """The original visual belongs in the article body, even with a custom share card."""
    if kind in ("websites","sections"):
        return public_image(item.get("screenshot_url"))
    if kind=="insights":
        cover=public_image(item.get("cover_image"))
        if cover:return cover
        site_slug=item.get("cover_site")
        if isinstance(site_slug,str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,110}",site_slug):
            # Bundled case screenshots are authoritative for editorial cover art.
            # A missing source record must never substitute an unrelated site.
            original="/screenshots/sites/"+site_slug+".webp"
            if (BASE/original.lstrip("/")).is_file():
                return original
        site=collection["sites"].get(site_slug)
        return public_image(site.get("screenshot_url")) if isinstance(site,dict) else None
    if kind=="patterns":
        for mid in item.get("modules",[]) if isinstance(item.get("modules"),list) else []:
            module=collection["modules"].get(mid)
            if isinstance(module,dict):
                cover=public_image(module.get("screenshot_url"))
                if cover:return cover
    return None


def _paragraph(value,limit=2000):
    if not isinstance(value,str) or not value.strip():return ""
    # The article editor supports **emphasis**; keep crawler HTML readable
    # without interpreting untrusted HTML or arbitrary Markdown links.
    escaped=safe(value,limit)
    emphasized=re.sub(r"\*\*(.{1,500}?)\*\*",r"<strong>\1</strong>",escaped)
    return "<p>"+emphasized+"</p>"


def _bullet_list(values,limit=12):
    if not isinstance(values,list):return ""
    items=[safe(x,650) for x in values[:limit] if isinstance(x,str) and x.strip()]
    return "<ul>"+"".join("<li>"+x+"</li>" for x in items)+"</ul>" if items else ""


def _research_table(rows):
    """Preserve readable, semantic comparison tables in crawler HTML."""
    if not isinstance(rows,list) or not rows:return ""
    normalized=[r[:8] for r in rows[:40] if isinstance(r,list) and r]
    if not normalized:return ""
    width=len(normalized[0])
    header="<thead><tr>"+''.join('<th scope="col">'+safe(str(cell),550)+'</th>' for cell in normalized[0])+"</tr></thead>"
    body="<tbody>"+''.join("<tr>"+''.join(
        "<td>"+safe(str(row[i]) if i<len(row) else "",850)+"</td>"
        for i in range(width))+"</tr>" for row in normalized[1:])+"</tbody>"
    return '<div role="region" aria-label="研究对比表格"><table>'+header+body+"</table></div>"


def source_url(value):
    """Recognize external reference URLs without performing network requests."""
    if not isinstance(value,str) or len(value)>650 or not re.fullmatch(r"https?://[^<>\s\"'\\]+",value,re.I):
        return None
    from urllib.parse import urlsplit
    try:
        parsed=urlsplit(value)
        if not parsed.hostname or parsed.username or parsed.password:
            return None
    except ValueError:
        return None
    return value


def article_sources(item,collection,limit=24):
    """Sources from explicit research links and referenced public websites.

    References are drawn only from published catalog snapshots; other content,
    hidden drafts and non-HTTP schemes never become citations.
    """
    sources=[]
    seen=set()
    if not isinstance(item,dict) or not isinstance(collection,dict):return sources
    sections=item.get("sections") if isinstance(item.get("sections"),list) else []
    for section in sections:
        if not isinstance(section,dict):continue
        for block in section.get("blocks",[]) if isinstance(section.get("blocks"),list) else []:
            if not isinstance(block,dict) or block.get("type")!="link":continue
            url=source_url(block.get("url"))
            if url and url not in seen:
                sources.append((str(block.get("text") or "参考资料")[:200],url))
                seen.add(url)
            if len(sources)>=limit:return sources
    sites=collection.get("sites",{})
    for ref in item.get("references",[]) if isinstance(item.get("references"),list) else []:
        if not isinstance(ref,(tuple,list)) or len(ref)<2 or ref[0]!="website":continue
        source=sites.get(ref[1]) if isinstance(sites,dict) and isinstance(ref[1],str) else None
        if not isinstance(source,dict):continue
        url=source_url(source.get("url"))
        if url and url not in seen:
            sources.append(("原始案例网站 · "+str(source.get("name") or ref[1])[:140],url))
            seen.add(url)
        if len(sources)>=limit:break
    return sources


def _record_link(kind, slug, item):
    if not isinstance(slug,str) or not _SLUG.fullmatch(slug) or not isinstance(item,dict):
        return ""
    name=item.get("name") if kind=="websites" else item.get("title")
    description=item.get("summary") or item.get("lesson") or item.get("question") or item.get("subtitle")
    return ('<li><a href="/'+kind+'/'+slug+'">'+safe(name or slug,180)+'</a>'
            +_paragraph(description,250)+'</li>')


def _linked_research(kind, entries, title, limit=8):
    """Cross-link only resources already present in the published catalog."""
    links=[]
    for slug,item in entries:
        if len(links)>=limit:break
        entry=_record_link(kind,slug,item)
        if entry:links.append(entry)
    if not links:return ""
    return '<section><h2>'+safe(title,100)+'</h2><ul>'+''.join(links)+'</ul></section>'


def public_prerender(path, record, collection):
    """Serve meaningful, escaped body text without relying on JavaScript execution.

    Hydrated SPA replaces this content when ready. Only the published catalog
    is passed here; no drafts, profile data, or private collection is included.
    """
    if not record or not record.get("indexed") or collection is None:return ""
    nav='<nav aria-label="设计研究目录"><a href="/websites">网站案例</a> · <a href="/sections">页面模块</a> · <a href="/patterns">设计模式</a> · <a href="/insights">研究文章</a></nav>'
    sections={"websites":"sites","sections":"modules","patterns":"patterns","insights":"articles"}
    parts=[x for x in path.strip("/").split("/") if x]
    if not parts:
        groups=[]
        for route,key in sections.items():
            label=PUBLIC[route][0]
            entries=list(collection[key].items())[:12]
            groups.append('<section><h2><a href="/'+route+'">'+safe(label,120)+'</a></h2><ul>'
                          +''.join(_record_link(route,slug,item) for slug,item in entries)+'</ul></section>')
        return '<div class="shell listing seo-prerender"><h1>真实 B2B 网站与设计研究资料库</h1>'+_paragraph(record["description"])+nav+''.join(groups)+'</div>'
    kind=parts[0]
    if kind not in sections:return ""
    entries=collection[sections[kind]]
    if len(parts)==1:
        return ('<div class="shell listing seo-prerender"><h1>'+safe(record["title"],180)+'</h1>'
                +_paragraph(record["description"])+nav+'<ul>'
                +''.join(_record_link(kind,slug,item) for slug,item in list(entries.items())[:100])
                +'</ul></div>')
    if len(parts)!=2:return ""
    item=entries.get(parts[1])
    if not isinstance(item,dict):return ""
    title=item.get("name") if kind=="websites" else item.get("title")
    out=['<div class="shell listing seo-prerender"><nav aria-label="面包屑"><a href="/">首页</a> / <a href="/'
         +kind+'">'+safe(PUBLIC[kind][0],130)+'</a></nav><article><h1>'+safe(title or parts[1],220)+'</h1>']
    image=content_image(kind,item,collection)
    if image:
        out.append('<figure><img src="'+safe(image,550)+'" loading="lazy" alt="'+safe(title or "页面研究截图",200)+'"></figure>')
    if kind=="websites":
        for key,label in (("sector","行业"),("summary","研究概述"),("focus","业务聚焦"),
                          ("model","商业模式"),("visual_style","视觉风格"),("takeaway","设计启示")):
            if item.get(key):
                out.append('<section><h2>'+label+'</h2>'+_paragraph(item[key])+'</section>')
        strengths=_bullet_list(item.get("design_strengths"))
        if strengths:out.append('<section><h2>设计优势</h2>'+strengths+'</section>')
        url=item.get("url")
        if isinstance(url,str) and re.fullmatch(r"https?://[^<>\s\"']+",url,re.I):
            out.append('<p>原始网站：<a rel="nofollow noopener noreferrer" href="'+safe(url,550)+'">'+safe(url,400)+'</a></p>')
        out.append(_linked_research("sections",
            ((mid,mod) for mid,mod in collection["modules"].items()
             if isinstance(mod,dict) and mod.get("site_id")==parts[1]),
            "此网站的页面模块"))
    elif kind=="sections":
        for key,label in (("category","模块分类"),("lesson","设计要点"),("summary","模块说明")):
            if item.get(key):out.append('<section><h2>'+label+'</h2>'+_paragraph(item[key])+'</section>')
        site=item.get("site_id")
        if isinstance(site,str) and _SLUG.fullmatch(site) and site in collection["sites"]:
            out.append('<p>关联案例：<a href="/websites/'+site+'">'+safe(collection["sites"][site].get("name",site))+'</a></p>')
        out.append(_linked_research("patterns",
            ((pid,p) for pid,p in collection["patterns"].items()
             if isinstance(p,dict) and isinstance(p.get("modules"),list) and parts[1] in p["modules"]),
            "运用此模块的设计模式"))
    elif kind=="patterns":
        for key,label in (("family","设计类型"),("question","设计问题"),("principle","核心原则"),
                          ("when","适用场景"),("compare","比较视角")):
            if item.get(key):out.append('<section><h2>'+label+'</h2>'+_paragraph(item[key])+'</section>')
        module_links=[]
        for mid in item.get("modules",[]) if isinstance(item.get("modules"),list) else []:
            if isinstance(mid,str) and _SLUG.fullmatch(mid) and mid in collection["modules"]:
                module_links.append('<li><a href="/sections/'+mid+'">'+safe(collection["modules"][mid].get("title",mid))+'</a></li>')
        if module_links:out.append('<section><h2>参考页面模块</h2><ul>'+''.join(module_links)+'</ul></section>')
    elif kind=="insights":
        if item.get("author"):out.append('<p>作者：'+safe(item["author"],150)+'</p>')
        if item.get("published_at"):out.append('<p>发布：'+safe(item["published_at"],20)+'</p>')
        out.append(_paragraph(item.get("subtitle")))
        points=_bullet_list(item.get("takeaways"))
        if points:out.append('<section><h2>核心观点</h2>'+points+'</section>')
        for i,section in enumerate(item.get("sections",[]) if isinstance(item.get("sections"),list) else []):
            if not isinstance(section,dict):continue
            out.append('<section><h2>'+safe(section.get("title") or "章节 "+str(i+1),200)+'</h2>')
            blocks=section.get("blocks")
            if isinstance(blocks,list):
                for block in blocks:
                    if not isinstance(block,dict):continue
                    t=block.get("type")
                    if t=="heading":out.append('<h3>'+safe(block.get("text"),500)+'</h3>')
                    elif t in ("paragraph","quote","callout"):out.append(_paragraph(block.get("text")))
                    elif t=="list":out.append(_bullet_list(block.get("items"),30))
                    elif t=="table":
                        table=_research_table(block.get("rows"))
                        if table:out.append(table)
                    elif t=="image":
                        image=public_image(block.get("src"))
                        if image:out.append('<figure><img loading="lazy" src="'+safe(image,550)+'" alt="'+safe(block.get("alt") or "文章配图",200)+'"></figure>')
                    elif t=="link":
                        external=block.get("url")
                        if isinstance(external,str) and re.fullmatch(r"https?://[^<>\s\"']+",external,re.I):
                            out.append('<p>参考链接：<a rel="nofollow noopener noreferrer" href="'+safe(external,550)+'">'+safe(block.get("text") or external,240)+'</a></p>')
            else:
                for text in section.get("paragraphs",[]) if isinstance(section.get("paragraphs"),list) else []:
                    out.append(_paragraph(text))
                out.append(_bullet_list(section.get("bullets"),30))
                out.append(_paragraph(section.get("callout")))
            out.append('</section>')
        refs=[]
        paths={"website":("websites","sites"),"module":("sections","modules"),"pattern":("patterns","patterns"),"article":("insights","articles")}
        for ref in item.get("references",[]) if isinstance(item.get("references"),list) else []:
            if not isinstance(ref,(list,tuple)) or len(ref)<2:continue
            r=paths.get(ref[0])
            if r and isinstance(ref[1],str) and _SLUG.fullmatch(ref[1]) and ref[1] in collection[r[1]]:
                target=collection[r[1]][ref[1]]
                name=target.get("name") if r[0]=="websites" else target.get("title")
                refs.append('<li><a href="/'+r[0]+'/'+ref[1]+'">'+safe(name or ref[1],220)+'</a></li>')
        if refs:out.append('<section><h2>相关研究与参考资料</h2><ul>'+''.join(refs)+'</ul></section>')
        sources=article_sources(item,collection)
        if sources:
            links=['<li><a href="'+safe(url,650)+'" rel="nofollow noopener noreferrer">'
                   +safe(label,200)+'</a></li>' for label,url in sources]
            out.append('<section aria-label="研究来源"><h2>参考资料与原始来源</h2>'
                       +'<p>资料链接供读者核对公开信息；案例观察不等于第三方性能验证。</p>'
                       +'<ul>'+''.join(links)+'</ul></section>')
    out.append('</article>'+nav+'</div>')
    return ''.join(out)


def seo_schema(path,record,collection,canonical,image):
    """Single route-aware JSON-LD node; avoid guessed performance claims."""
    parts=[x for x in path.strip("/").split("/") if x]
    base={"@context":"https://schema.org"}
    if not parts or len(parts)==1:
        item={"@type":"WebSite" if not parts else "CollectionPage",
              "name":"B2B Atlas" if not parts else record["title"],
              "url":ORIGIN+"/" if not parts else canonical,
              "description":record["description"],"inLanguage":"zh-CN"}
        if record.get("keywords"):item["keywords"]=record["keywords"]
        return {**base,**item}
    breadcrumbs={"@type":"BreadcrumbList","itemListElement":[
        {"@type":"ListItem","position":1,"name":"首页","item":ORIGIN+"/"},
        {"@type":"ListItem","position":2,"name":PUBLIC[parts[0]][0],"item":ORIGIN+"/"+parts[0]},
        {"@type":"ListItem","position":3,"name":record["title"],"item":canonical}]}
    if record.get("kind")!="article":
        webpage={"@type":"WebPage","name":record["title"],"url":canonical,
                 "description":record["description"],"inLanguage":"zh-CN",
                 "primaryImageOfPage":image,"breadcrumb":breadcrumbs}
        if record.get("keywords"):webpage["keywords"]=record["keywords"]
        return {**base,"@graph":[webpage,breadcrumbs]}
    article={"@type":"Article","headline":record["title"],"description":record["description"],
             "inLanguage":"zh-CN","author":{"@type":"Organization","name":record.get("author") or "B2B Atlas 编辑部"},
             "publisher":{"@type":"Organization","name":"B2B Atlas"},
             "mainEntityOfPage":canonical}
    if record.get("image"):article["image"]=image
    original=collection.get("articles",{}).get(parts[1]) if isinstance(collection,dict) else None
    if original:
        citations=[url for _label,url in article_sources(original,collection)]
        if citations:article["citation"]=citations
    if record.get("keywords"):article["keywords"]=record["keywords"]
    published=record.get("published")
    if isinstance(published,str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}",published):
        article["datePublished"]=published
    modified=original.get("updated_at") if isinstance(original,dict) else None
    if isinstance(modified,str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}",modified) and (not published or modified>=published):
        article["dateModified"]=modified
    return {**base,"@graph":[article,breadcrumbs]}


def seo_document(full_path):
    clean="/"+full_path.strip("/") if full_path.strip("/") else "/"
    parts=[part for part in clean.strip("/").split("/") if part]
    collection=catalog() if (not parts or parts[0] in PUBLIC) else None
    page_overrides=read_page_seo() if collection is not None else {}
    record=seo_record(clean,collection,page_overrides)
    found=record is not None
    if not found:record={"title":"404 · 页面未找到","description":"页面不存在或已移动。探索 B2B Atlas 的网站、页面模块和设计文章。","path":clean,"indexed":False}
    canonical=ORIGIN+record["path"]
    title=record["title"] if record["title"].startswith("B2B Atlas") else record["title"]+" · B2B Atlas"
    desc=record["description"]
    template=(STATIC/"index.html").read_text(encoding="utf-8")
    template=re.sub(r"<title>.*?</title>","<title>"+safe(title,220)+"</title>",template,count=1,flags=re.S)
    template=re.sub(r'<meta name="description" content="[^"]*">','<meta name="description" content="'+safe(desc,270)+'">',template,count=1)
    image=ORIGIN+(record.get("image") or "/assets/visual-placeholder.svg")
    extras=(
        ('<link rel="canonical" href="'+safe(canonical,650)+'">' if record["indexed"] else '')
        '<meta name="robots" content="'+("index, follow" if record["indexed"] else "noindex, follow")+'">'
        '<meta property="og:type" content="'+("article" if record.get("kind")=="article" else "website")+'">'
        '<meta property="og:site_name" content="B2B Atlas">'
        '<meta property="og:title" content="'+safe(title,220)+'">'
        '<meta property="og:description" content="'+safe(desc,270)+'">'
        '<meta property="og:url" content="'+safe(canonical,650)+'">'
        '<meta property="og:image" content="'+safe(image,650)+'">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<meta name="twitter:image" content="'+safe(image,650)+'">'
    )
    if record["indexed"]:
        data=seo_schema(clean,record,collection,canonical,image)
        extras+='<script id="atlas-seo-schema" type="application/ld+json">'+json.dumps(data,ensure_ascii=False).replace("<","\\u003c")+'</script>'
    # Hydration must keep title/description/image identical to server response.
    settings_json=json.dumps(page_overrides,ensure_ascii=False).replace("<","\\u003c").replace("&","\\u0026")
    extras+='<script id="atlas-page-seo-data" type="application/json">'+settings_json+'</script>'
    template=template.replace("</head>",extras+"</head>",1)
    prerender=public_prerender(clean,record,collection)
    if prerender:
        template=template.replace('<div class="shell loading">正在加载设计资源…</div>',prerender,1)
    headers={"Cache-Control":"no-cache","X-Robots-Tag":"noindex" if not record["indexed"] else "index, follow"}
    return HTMLResponse(template,status_code=200 if found else 404,headers=headers)

def register_seo_routes(app:FastAPI):
    @app.get("/robots.txt",include_in_schema=False)
    def robots():
        return PlainTextResponse("User-agent: *\nDisallow: /admin\nDisallow: /account\nDisallow: /collections\nDisallow: /board\nDisallow: /login\nDisallow: /register\nDisallow: /forgot-password\nDisallow: /reset-password\nDisallow: /compare\nSitemap: "+ORIGIN+"/sitemap.xml\n",headers={"Cache-Control":"public, max-age=3600"})
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
