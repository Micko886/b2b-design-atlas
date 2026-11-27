"""V64 public index: stable HTML discovery pages for published resources only.

These pages are distinct from the interactive masonry browsing experience.
No drafts or personal data enter this module: callers pass seo_routes.catalog().
"""
from __future__ import annotations
import math
import re

PAGE_SIZE=60
KINDS={
    "websites":("sites","网站案例"),
    "sections":("modules","页面模块"),
    "patterns":("patterns","设计模式"),
    "insights":("articles","研究文章")
}
STYLE="""<style id="atlas-directory-style">
.atlas-directory{padding:44px 0 80px;max-width:1040px}
.atlas-directory-intro{border-bottom:1px solid #dce4ef;padding-bottom:28px;margin-bottom:32px}
.atlas-directory-eyebrow{font-size:11px!important;letter-spacing:.14em;text-transform:uppercase;color:#426be0!important;font-weight:800}
.atlas-directory h1{font-size:clamp(28px,4vw,44px);line-height:1.2;letter-spacing:-.04em;margin:12px 0}
.atlas-directory h2{font-size:22px;margin:0 0 20px}
.atlas-directory p{line-height:1.7;color:#66758b}
.atlas-directory a{color:#2155c8;text-decoration:none}
.atlas-directory a:hover{text-decoration:underline}
.atlas-directory-categories,.atlas-directory-entries{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.atlas-directory-categories li,.atlas-directory-entries li{min-width:0;padding:17px 19px;border:1px solid #e0e7f2;border-radius:12px;background:#fff}
.atlas-directory-entries li a{font-weight:750}
.atlas-directory-entries li p{margin:9px 0 0;font-size:13px;color:#69778b;overflow-wrap:anywhere}
.atlas-directory-categories li a{display:block;font-weight:750}
.atlas-directory-categories li span,.atlas-directory-count{font-size:13px;color:#67768b}
.atlas-directory-categories li span{display:block;margin-top:7px}
.atlas-directory-pagination{display:flex;flex-wrap:wrap;gap:9px;align-items:center;justify-content:center;margin-top:32px}
.atlas-directory-pagination a,.atlas-directory-pagination span{padding:9px 12px;border:1px solid #dce4f0;border-radius:8px}
.atlas-directory-pagination [aria-current]{background:#2155c8;color:#fff;border-color:#2155c8}
.atlas-directory-note{font-size:12px;margin-top:30px}
@media(max-width:720px){.atlas-directory{padding:25px 0 50px}
.atlas-directory-categories,.atlas-directory-entries{grid-template-columns:1fr}
.atlas-directory-categories li,.atlas-directory-entries li{padding:15px}}
</style>"""


def entries(collection,kind):
    """Only valid slugs in the published catalog, sorted consistently."""
    from app import seo_routes as seo
    rows=collection.get(KINDS[kind][0],{}) if isinstance(collection,dict) else {}
    if not isinstance(rows,dict):return []
    valid=[(slug,item) for slug,item in rows.items()
           if isinstance(slug,str) and seo._SLUG.fullmatch(slug) and isinstance(item,dict)]
    return sorted(valid,key=lambda pair:(
        str((pair[1].get("name") if kind=="websites" else pair[1].get("title")) or "").casefold(),pair[0]))


def page_count(collection,kind):
    return max(1,math.ceil(len(entries(collection,kind))/PAGE_SIZE))


def record(parts,collection):
    if parts==["directory"]:
        return {"title":"全部公开研究资源索引",
                "description":"按栏目和页码查找 B2B Atlas 已发布的网站案例、页面模块、设计模式与研究文章。",
                "path":"/directory","indexed":True,"kind":"directory"}
    if len(parts)!=3 or parts[0]!="directory" or parts[1] not in KINDS:
        return None
    kind,n=parts[1],parts[2]
    if not re.fullmatch(r"[1-9][0-9]{0,5}",n):return None
    if int(n)>page_count(collection,kind):return None
    title=KINDS[kind][1]
    return {"title":title+" · 公开资源目录 · 第 "+n+" 页",
            "description":"浏览已发布的"+title+"；当前为第 "+n+" 页，共 "+str(page_count(collection,kind))+" 页。每条资料可打开独立研究页面。",
            "path":"/directory/"+kind+"/"+n,"indexed":True,"kind":"directory"}


def sitemap_entries(collection):
    yield "/directory",None
    for kind in KINDS:
        for page in range(1,page_count(collection,kind)+1):
            yield "/directory/"+kind+"/"+str(page),None


def prerender(path,record,collection):
    from app import seo_routes as seo
    parts=[part for part in path.strip("/").split("/") if part]
    intro=('<div class="shell atlas-directory"><div class="atlas-directory-intro">'
           '<p class="atlas-directory-eyebrow">PUBLIC RESOURCE INDEX / B2B ATLAS</p>'
           '<h1>'+seo.safe(record["title"],220)+'</h1>'
           '<p>'+seo.safe(record["description"],300)+'</p>'
           '<p><a href="/">首页</a> / <a href="/directory">全部公开资源索引</a></p></div>')
    if len(parts)==1:
        groups=[]
        for kind,(_key,label) in KINDS.items():
            rows=entries(collection,kind)
            groups.append('<li><a href="/directory/'+kind+'/1">'+seo.safe(label,120)+'</a>'
                          '<span>'+str(len(rows))+' 条已发布资源 · '+str(page_count(collection,kind))+' 页</span></li>')
        return (intro+'<section><h2>按栏目浏览</h2><ul class="atlas-directory-categories">'
                +''.join(groups)+'</ul></section><p class="atlas-directory-note">'
                '此目录仅收录正式发布的公开资料，不包括审核中的草稿和个人内容。</p></div>')
    kind,page=parts[1],int(parts[2])
    rows=entries(collection,kind)
    selected=rows[(page-1)*PAGE_SIZE:page*PAGE_SIZE]
    total=page_count(collection,kind)
    pagination=['<nav class="atlas-directory-pagination" aria-label="资源目录分页">']
    if page>1:
        pagination.append('<a rel="prev" href="/directory/'+kind+'/'+str(page-1)+'">← 上一页</a>')
    for p in range(1,total+1):
        pagination.append('<span aria-current="page">'+str(p)+'</span>' if p==page
                          else '<a href="/directory/'+kind+'/'+str(p)+'">'+str(p)+'</a>')
    if page<total:
        pagination.append('<a rel="next" href="/directory/'+kind+'/'+str(page+1)+'">下一页 →</a>')
    pagination.append('</nav>')
    return (intro+'<p class="atlas-directory-count">共 '+str(len(rows))+' 条已发布资料 · 第 '
            +str(page)+' / '+str(total)+' 页</p><ul class="atlas-directory-entries">'
            +''.join(seo._record_link(kind,slug,item) for slug,item in selected)
            +'</ul>'+''.join(pagination)
            +'<p class="atlas-directory-note">目录仅包含公开发布的资源；可从标题进入完整研究页面。</p></div>')
