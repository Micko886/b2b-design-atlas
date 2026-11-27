"""V74: final editorial quality and explicit cross-reference audit.

Read-only, published-only. The public directory already links to all listed
resources: an unreferenced editorial record is NOT an SEO crawl orphan.
No HTTP requests are made to third-party source URLs.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from fastapi import FastAPI,Request
from app import cms_quality,cms_routes,seo_routes,user_auth

KINDS=("site","module","pattern","article")
REFERENCE_KIND={"website":"site","module":"module","pattern":"pattern","article":"article"}
PAGE_ROUTE={kind:"/"+route+"/" for kind,(_,route) in cms_quality._KIND_MAP.items()}
LABELS={**cms_quality._ISSUE_LABELS,
        "contextual_links":"缺少编辑关联","depth":"内容分析仍需补充",
        "broken_refs":"关联资料已下线或无效"}
MAX_PAGE=60


def published_maps(collection):
    """Only valid, published records can appear as graph nodes."""
    output={}
    for kind in KINDS:
        group=collection.get(cms_quality._KIND_MAP[kind][0],{}) if isinstance(collection,dict) else {}
        group=group if isinstance(group,dict) else {}
        output[kind]={slug:content for slug,content in group.items()
                      if isinstance(slug,str) and cms_routes.SLUG.fullmatch(slug)
                      and isinstance(content,dict)}
    return output


def editorial_graph(public):
    """Count only explicit, valid editorial relations, not all directory links."""
    incoming=defaultdict(set)
    outbound=defaultdict(set)
    broken=defaultdict(set)
    def connect(source,target):
        if source==target:return
        outbound[source].add(target)
        incoming[target].add(source)
    for slug,module in public["module"].items():
        source=("module",slug)
        site=module.get("site_id")
        if isinstance(site,str) and site in public["site"]:
            connect(source,("site",site))
        elif site:
            broken[source].add("site:"+str(site)[:100])
    for slug,pattern in public["pattern"].items():
        source=("pattern",slug)
        modules=pattern.get("modules")
        if not isinstance(modules,list):
            if modules:broken[source].add("modules:invalid")
            continue
        for mid in modules:
            if isinstance(mid,str) and mid in public["module"]:
                connect(source,("module",mid))
            else:broken[source].add("module:"+str(mid)[:100])
    for slug,article in public["article"].items():
        source=("article",slug)
        raw=article.get("references")
        if not isinstance(raw,list):
            if raw:broken[source].add("references:invalid")
            continue
        for entry in raw:
            if not isinstance(entry,(list,tuple)) or len(entry)!=2:
                broken[source].add("reference:invalid")
                continue
            kind=REFERENCE_KIND.get(entry[0]) if isinstance(entry[0],str) else None
            ref=entry[1]
            if kind and isinstance(ref,str) and ref in public[kind] and (kind,ref)!=source:
                connect(source,(kind,ref))
            else:broken[source].add(str(entry[0])[:45]+":"+str(ref)[:90])
    return incoming,outbound,broken


def reading_depth(kind,item):
    if kind=="site":
        fields=("summary","focus","model","design_lessons","visual_style",
                "business_focus","business_model","strengths","insights")
        threshold=95
    elif kind=="module":
        fields=("summary","lesson","focus","description","design_notes","analysis")
        threshold=65
    elif kind=="pattern":
        fields=("question","principle","when","example","summary","description",
                "application","tradeoffs")
        threshold=100
    else:return None
    count=0
    for key in fields:
        val=item.get(key)
        if isinstance(val,str):count+=len(val.strip())
        elif isinstance(val,list):count+=sum(len(x.strip()) for x in val if isinstance(x,str))
    return count,threshold


def analyze(collection,kind_filter=None,offset=0,limit=12):
    if kind_filter and kind_filter not in KINDS:
        user_auth.error(422,"未知内容栏目。")
    if not isinstance(offset,int) or offset<0 or not isinstance(limit,int) or not 1<=limit<=MAX_PAGE:
        user_auth.error(422,"分页参数不合法。")
    public=published_maps(collection)
    incoming,outbound,broken=editorial_graph(public)
    duplicates={kind:cms_quality.duplicate_map(kind,collection) for kind in KINDS}
    all_rows=[]
    frequency=Counter()
    kind_stats=[]
    count_broken=count_weak=count_unlinked=0
    for kind in KINDS:
        total=flagged=urgent=0
        for slug,item in sorted(public[kind].items()):
            total+=1
            key=(kind,slug)
            review=cms_quality.audit_resource(kind,slug,item,collection,duplicates[kind].get(slug))
            issues=list(review["issues"])
            existing={x["code"] for x in issues}
            if broken.get(key) and "broken_refs" not in existing:
                names=sorted(broken[key])
                issues.append({"code":"broken_refs",
                               "label":"存在 "+str(len(names))+" 条无法对应已发布内容的关联",
                               "advice":"核实并更新 "+", ".join(names[:3])+"；删除无效标识或重新选择公开记录。",
                               "priority":"high"})
            depth=reading_depth(kind,item)
            if depth and depth[0]<depth[1] and "depth" not in existing:
                issues.append({"code":"depth","label":"内容分析和证据偏少",
                               "advice":"完善真实观察、适用场景和设计依据（当前约 "+str(depth[0])+
                                        " 字），不要为凑字数重复内容。",
                               "priority":"normal"})
            # Directory/collection pages already expose these URLs. Here we
            # signal missing contextual editorial references only.
            if not incoming.get(key):
                issues.append({"code":"contextual_links",
                               "label":"尚无其他已发布研究资料明确关联此条内容",
                               "advice":"可从已发布文章的参考资源或设计模式关联该记录；公开目录仍能访问，"
                                        "这不表示页面无法被爬取。",
                               "priority":"normal"})
            if not issues:continue
            flagged+=1
            is_high=any(x["priority"]=="high" for x in issues)
            urgent+=bool(is_high)
            codes={issue["code"] for issue in issues}
            count_broken+=("broken_refs" in codes)
            count_weak+=("depth" in codes)
            count_unlinked+=("contextual_links" in codes)
            for issue in issues:frequency[issue["code"]]+=1
            all_rows.append({"kind":kind,"slug":slug,"url":PAGE_ROUTE[kind]+slug,
                             "title":review["title"],"priority":"high" if is_high else "normal",
                             "issue_count":len(issues),"incoming_count":len(incoming.get(key,set())),
                             "outgoing_count":len(outbound.get(key,set())),
                             "issues":issues})
        kind_stats.append({"kind":kind,"label":cms_quality._KIND_LABELS[kind],
                           "total":total,"flagged":flagged,"high":urgent})
    all_rows.sort(key=lambda row:(row["priority"]!="high",-row["issue_count"],
                                  KINDS.index(row["kind"]),row["slug"]))
    visible=[row for row in all_rows if not kind_filter or row["kind"]==kind_filter]
    result={"total":sum(x["total"] for x in kind_stats),
            "flagged":len(all_rows),
            "high":sum(x["high"] for x in kind_stats),
            "broken_records":count_broken,"thin_records":count_weak,
            "unlinked_records":count_unlinked,
            "kind_stats":kind_stats,
            "top_issues":[{"code":code,"label":LABELS.get(code,code),"count":n}
                          for code,n in sorted(frequency.items(),key=lambda x:(-x[1],x[0]))[:10]],
            "kind":kind_filter or "all","matched":len(visible),
            "offset":offset,"limit":limit,
            "items":visible[offset:offset+limit],
            "has_more":offset+limit<len(visible),
            "note":"仅对现有公开数据做静态检查，未请求外部网站；"
                   "“缺少编辑关联”不等于 SEO 爬虫孤立，因为公开目录仍提供入口。"}
    return result


def register_final_routes(app:FastAPI):
    @app.get("/api/admin/seo/final-audit",include_in_schema=False)
    def final_audit(request:Request,kind:str="all",offset:int=0,limit:int=12):
        cms_routes.require_admin(request,permission="view")
        if kind!="all" and kind not in KINDS:user_auth.error(422,"未知内容栏目。")
        return analyze(seo_routes.catalog(),None if kind=="all" else kind,offset,limit)
