"""V69: editorial industry topic landing pages backed by approved public studies.

No keyword-driven page factory. Only three individually authored, source-backed
topics appear while their flagship study AND cited website remain published.
"""
from __future__ import annotations

TOPICS={
    "manufacturing":{
        "article":"industry-manufacturing-web-experience",
        "name":"制造业",
        "title":"制造业 B2B 官网设计与询价路径研究",
        "description":"从制造能力、技术约束、质量依据到 RFQ 询价流程，研究制造业网站怎样组织采购与工程人员需要的信息。",
        "lead":"制造业官网不只是设备展示册。工程团队关心工艺、材料、公差与质量，采购团队还需要报价步骤、交期说明以及可核对的服务边界。",
        "questions":["客户能否快速确认工艺与材料是否适配？","报价前需准备的文件和规格是否明确？","验证材料能否对应具体生产能力与业务场景？"]
    },
    "robotics":{
        "article":"industry-robotics-web-experience",
        "name":"机器人",
        "title":"机器人 B2B 官网设计与能力证据研究",
        "description":"研究机器人网站如何区分演示镜头、产品能力、应用任务与部署限制，并将硬件、软件和场景内容连接起来。",
        "lead":"机器人官网常以动态演示抓住注意力，但视频展示的动作、已公开的产品能力与实际部署条件并不等价。阅读网站时应同时寻找场景边界和出处。",
        "questions":["演示对应的任务条件和适用边界是否清晰？","硬件、软件、场景与部署信息能否互相印证？","视觉表达是否区分演示与可核验事实？"]
    },
    "automation":{
        "article":"industry-automation-web-experience",
        "name":"工业自动化",
        "title":"工业自动化官网设计与设备选型研究",
        "description":"研究工业自动化网站如何同时支持设备型号、工程任务与系统架构的浏览路径，并解释集成和部署信息。",
        "lead":"自动化设备的选型可能从型号、系统兼容性或目标任务开始。有效的网站结构应让不同角色找到同一个方案的组成关系，而非只看到漂亮的产品图。",
        "questions":["能否按设备、应用任务与系统架构进入？","产品规格、兼容性及集成步骤是否可交叉查找？","方案说明是否明确来源与适用边界？"]
    }
}
REFERENCE_TYPES={
    "website":("sites","websites","网站案例"),
    "module":("modules","sections","页面模块"),
    "pattern":("patterns","patterns","设计模式"),
    "article":("articles","insights","延伸研究")
}
STYLE="""<style id="atlas-topics-style">
.atlas-topics{max-width:1100px;padding:48px 0 85px}
.atlas-topics a{color:#2355cc;text-decoration:none}
.atlas-topics a:hover{text-decoration:underline}
.atlas-topics .topics-kicker{font-size:11px;font-weight:800;letter-spacing:.14em;color:#2759cb;margin:0 0 10px}
.atlas-topics .topics-breadcrumb{font-size:12px;margin:0 0 26px;color:#8290a7}
.atlas-topics h1{font-size:clamp(32px,4vw,50px);letter-spacing:-.05em;line-height:1.16;margin:0 0 18px}
.atlas-topics .topics-lead{font-size:17px;line-height:1.85;color:#485874;max-width:850px;margin:0 0 30px}
.atlas-topics h2{font-size:22px;letter-spacing:-.025em;margin:0 0 18px}
.atlas-topics h3{font-size:16px;margin:0 0 10px;line-height:1.5}
.atlas-topics section{padding:27px 0;border-top:1px solid #e0e7f1}
.atlas-topics p,.atlas-topics li{line-height:1.75;color:#59677e}
.atlas-topics .topics-cards{padding:0;list-style:none;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}
.atlas-topics .topics-cards>li{border:1px solid #dde6f4;border-radius:13px;background:#fff;padding:20px}
.atlas-topics .topics-cards strong{font-size:17px;display:block;margin:0 0 12px;color:#1e3a70}
.atlas-topics .topics-cards p{font-size:13px;margin:8px 0 0}
.atlas-topics .topics-feature{background:#f3f6fc;border-radius:14px;padding:22px;margin:14px 0 0}
.atlas-topics .topics-feature a{font-weight:750}
.atlas-topics .topics-feature p{margin:8px 0 0}
.atlas-topics .topics-questions{padding-left:23px;margin:8px 0 0}
.atlas-topics .topics-related{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 28px;padding-left:20px}
.atlas-topics .topics-note{font-size:13px;margin-top:22px}
@media(max-width:730px){.atlas-topics{padding:28px 0 54px}
.atlas-topics .topics-cards,.atlas-topics .topics-related{grid-template-columns:1fr}
.atlas-topics .topics-cards>li{padding:17px}.atlas-topics .topics-lead{font-size:15px}}
</style>"""


def study(collection,slug):
    """Require verifiable existing article plus one cited published website."""
    info=TOPICS.get(slug)
    if not info or not isinstance(collection,dict):return None
    articles=collection.get("articles",{})
    if not isinstance(articles,dict):return None
    a=articles.get(info["article"])
    if not isinstance(a,dict) or a.get("industry_topic")!=slug or not str(a.get("title") or "").strip():
        return None
    refs=references(collection,a)
    if not any(kind=="website" for kind,_,_ in refs):return None
    if len(refs)<2:return None
    return a


def references(collection,article):
    """Only explicit article citations resolved within approved public maps."""
    from app import seo_routes
    matches=[]
    used=set()
    raw=article.get("references",[]) if isinstance(article,dict) else []
    for ref in raw if isinstance(raw,list) else []:
        if not isinstance(ref,(list,tuple)) or len(ref)!=2:continue
        kind,slug=ref
        if kind not in REFERENCE_TYPES or not isinstance(slug,str) or not seo_routes._SLUG.fullmatch(slug):
            continue
        key,route,_label=REFERENCE_TYPES[kind]
        item=collection.get(key,{}) if isinstance(collection,dict) else {}
        item=item.get(slug) if isinstance(item,dict) else None
        if not isinstance(item,dict) or (kind,slug) in used:continue
        name=item.get("name") if kind=="website" else item.get("title")
        if not isinstance(name,str) or not name.strip():continue
        used.add((kind,slug))
        matches.append((kind,slug,item))
    return matches


def live_topics(collection):
    return [(slug,info) for slug,info in TOPICS.items() if study(collection,slug) is not None]


def record(parts,collection):
    if parts==["topics"]:
        if not live_topics(collection):return None
        return {"title":"B2B 行业网站研究专题",
                "description":"按制造业、机器人和工业自动化三个有公开案例和引用依据的研究专题，探索网站信息架构、信任证据和转化路径。",
                "path":"/topics","indexed":True,"kind":"topic"}
    if len(parts)!=2 or parts[0]!="topics":return None
    slug=parts[1]
    a=study(collection,slug)
    if a is None:return None
    info=TOPICS[slug]
    return {"title":info["title"],"description":info["description"],
            "path":"/topics/"+slug,"indexed":True,"kind":"topic",
            "keywords":info["name"]+" B2B 官网, 设计研究",
            "topic":slug}


def sitemap_entries(collection):
    current=live_topics(collection)
    if current:
        yield "/topics",None
        for slug,_ in current:
            yield "/topics/"+slug,None


def _links(collection,article):
    result=[]
    for kind,slug,item in references(collection,article):
        _key,route,label=REFERENCE_TYPES[kind]
        title=item.get("name") if kind=="website" else item.get("title")
        description=item.get("summary") or item.get("question") or item.get("lesson") or item.get("subtitle")
        result.append({"kind":kind,"path":"/"+route+"/"+slug,"name":title,
                       "label":label,"description":description or ""})
    return result


def schema(record,collection,origin):
    """CollectionPage with real linked ItemList, not invented reviews/results."""
    from app import seo_routes
    path=record["path"]
    data={"@context":"https://schema.org","@type":"CollectionPage",
          "name":record["title"],"url":origin+path,
          "description":record["description"],"inLanguage":"zh-CN"}
    if path=="/topics":
        links=[{"name":info["title"],"path":"/topics/"+slug} for slug,info in live_topics(collection)]
    else:
        article=study(collection,record["topic"])
        links=([{"name":article["title"],"path":"/insights/"+TOPICS[record["topic"]]["article"]}]
               +_links(collection,article))
    data["mainEntity"]={"@type":"ItemList","itemListElement":[
        {"@type":"ListItem","position":i,"name":link["name"],"url":origin+link["path"]}
        for i,link in enumerate(links[:30],1)]}
    data["breadcrumb"]={"@type":"BreadcrumbList","itemListElement":[
        {"@type":"ListItem","position":1,"name":"首页","item":origin+"/"},
        {"@type":"ListItem","position":2,"name":"行业研究专题","item":origin+"/topics"}
    ]+([{"@type":"ListItem","position":3,"name":record["title"],"item":origin+path}]
       if path!="/topics" else [])}
    return data


def prerender(path,record,collection):
    """Readable HTML without JS, based on explicit, published research links."""
    from app import seo_routes as seo
    if path=="/topics":
        cards=[]
        for slug,info in live_topics(collection):
            article=study(collection,slug)
            links=_links(collection,article)
            count=sum(link["kind"]=="website" for link in links)
            cards.append('<li><strong>'+seo.safe(info["name"])+'</strong>'
                         '<h2><a href="/topics/'+slug+'">'+seo.safe(info["title"])+'</a></h2>'
                         '<p>'+seo.safe(info["description"],300)+'</p>'
                         '<p>'+str(count)+' 个已发布来源案例 · 1 篇行业研究</p></li>')
        return ('<div class="shell atlas-topics" aria-label="行业专题">'
                '<p class="topics-kicker">INDUSTRY / RESEARCH</p>'
                '<p class="topics-breadcrumb"><a href="/">首页</a> / 行业专题</p>'
                '<h1>'+seo.safe(record["title"])+'</h1>'
                '<p class="topics-lead">'+seo.safe(record["description"])+'</p>'
                '<section><h2>按真实案例进入行业研究</h2><ul class="topics-cards">'
                +''.join(cards)+'</ul></section>'
                '<p class="topics-note"><a href="/methodology">研究方法与引用说明</a> · <a href="/directory">全部公开资源目录</a></p></div>')
    slug=record["topic"]
    info=TOPICS[slug]
    article=study(collection,slug)
    refs=_links(collection,article)
    grouped=[]
    for kind,(_key,_route,label) in REFERENCE_TYPES.items():
        related=[ref for ref in refs if ref["kind"]==kind]
        if not related:continue
        grouped.append('<section><h2>'+seo.safe(label)+'</h2><ul class="topics-cards">'
                       +''.join('<li><h3><a href="'+ref["path"]+'">'+seo.safe(ref["name"],200)+'</a></h3>'
                                +('<p>'+seo.safe(ref["description"],280)+'</p>' if ref["description"] else '')
                                +'</li>' for ref in related[:12])+'</ul></section>')
    conclusions=article.get("takeaways",[])
    conclusions=conclusions if isinstance(conclusions,list) else []
    takeaways=''.join('<li>'+seo.safe(v,450)+'</li>' for v in conclusions[:6] if isinstance(v,str) and v.strip())
    questions=''.join('<li>'+seo.safe(v,220)+'</li>' for v in info["questions"])
    siblings=''.join('<li><a href="/topics/'+s+'">'+seo.safe(data["name"])+'</a></li>'
                     for s,data in live_topics(collection) if s!=slug)
    return ('<div class="shell atlas-topics" aria-label="行业研究">'
            '<p class="topics-kicker">INDUSTRY / RESEARCH</p>'
            '<p class="topics-breadcrumb"><a href="/">首页</a> / <a href="/topics">行业专题</a> / '+seo.safe(info["name"])+'</p>'
            '<h1>'+seo.safe(info["title"],210)+'</h1>'
            '<p class="topics-lead">'+seo.safe(info["lead"],480)+'</p>'
            '<section><h2>研究关注的问题</h2><ol class="topics-questions">'+questions+'</ol></section>'
            '<section><h2>完整行业研究</h2><div class="topics-feature">'
            '<h3><a href="/insights/'+info["article"]+'">'+seo.safe(article["title"],210)+'</a></h3>'
            '<p>'+seo.safe(article.get("seo_description") or article.get("subtitle") or "",480)+'</p>'
            '</div></section>'
            +('<section><h2>研究结论与观察</h2><ul>'+takeaways+'</ul></section>' if takeaways else '')
            +''.join(grouped)
            +('<section><h2>其他行业专题</h2><ul class="topics-related">'+siblings+'</ul></section>' if siblings else '')
            '<p class="topics-note">第三方产品能力和商业表现需以原始来源为准。'
            '<a href="/methodology">阅读研究方法与引用说明</a>。</p>'
            '</div>')
