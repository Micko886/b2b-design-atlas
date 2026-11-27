"""V51.19 · Deterministic SEO and editorial preflight.

Checks are advisory and are not search-engine ranking promises. The endpoint
never publishes content. Validations in cms_routes remain authoritative.
"""
from __future__ import annotations
from fastapi import FastAPI,Request
from pydantic import BaseModel,Field
from app import cms_routes,user_auth

class SeoPreview(BaseModel):
    slug: str=Field(max_length=111)
    payload: dict

def quality_report(slug,payload):
    if not isinstance(payload,dict):payload={}
    title=str(payload.get("seo_title") or payload.get("title") or "").strip()
    description=str(payload.get("seo_description") or payload.get("subtitle") or "").strip()
    checks=[]
    def check(code,status,label,advice):
        checks.append({"code":code,"status":status,"label":label,"advice":advice})
    if not title:check("title","error","缺少 SEO 标题","请填写文章标题或独立 SEO 标题。")
    elif len(title)<16:check("title","warning","标题过短","建议使用能够说明文章主题的标题。")
    elif len(title)>70:check("title","warning","标题较长","搜索结果可能截断，建议压缩至 70 字符以内。")
    else:check("title","pass","标题长度合理","")
    if not description:check("description","error","缺少 SEO 描述","请填写文章摘要或独立 SEO 描述。")
    elif len(description)<50:check("description","warning","描述信息偏短","建议更完整地说明文章涵盖的研究主题。")
    elif len(description)>170:check("description","warning","描述信息过长","搜索结果可能截断，可适度精简。")
    else:check("description","pass","描述信息完整","")
    if not payload.get("cover_image") and not payload.get("cover_site"):
        check("cover","warning","未选择文章封面","建议选择清晰的原创或已授权媒体。")
    else:check("cover","pass","已配置封面素材","")
    if not payload.get("tags"):check("tags","warning","缺少主题标签","加入准确、不过度堆砌的研究关键词。")
    else:check("tags","pass","已标记研究主题","")
    sections=payload.get("sections",[])
    if not isinstance(sections,list) or not sections:
        check("body","error","文章没有正文章节","至少需要一章有效正文。")
    else:
        headings=[str(x.get("title","")).strip().casefold() for x in sections if isinstance(x,dict)]
        if len(headings)!=len(set(headings)):
            check("headings","warning","存在重复章节标题","建议各章使用不同的小标题。")
        else:check("headings","pass","章节层级清晰","")
        text=0
        images=[]
        for section in sections:
            if not isinstance(section,dict):continue
            if isinstance(section.get("blocks"),list):
                for block in section["blocks"]:
                    if not isinstance(block,dict):continue
                    text+=len(str(block.get("text",""))) + sum(len(str(v)) for v in block.get("items",[]))
                    if block.get("type")=="image":images.append(block)
            else:
                text+=sum(len(str(v)) for v in section.get("paragraphs",[]))
                if section.get("image"):images.append({"src":section["image"],"alt":section.get("image_caption","")})
        if text<200:check("depth","warning","文章主体文字较少","建议加入更完整的实际案例、分析和结论。")
        else:check("depth","pass","文章具备一定内容深度","")
        missing_alt=sum(bool(img.get("src")) and not str(img.get("alt","")).strip() for img in images)
        if missing_alt:check("alt","warning",str(missing_alt)+" 张图片缺少替代文字","描述图片的重要信息，帮助无障碍访问。")
        elif images:check("alt","pass","正文图片有替代文字","")
    if not payload.get("references"):
        check("references","warning","尚无参考来源记录","如引用第三方资料，请补充可核验的来源信息。")
    else:check("references","pass","已有参考资料","")
    score=max(0,100-24*sum(x["status"]=="error" for x in checks)
              -8*sum(x["status"]=="warning" for x in checks))
    return {"score":score,"checks":checks,"title":title,"description":description,
            "canonical_path":"/insights/"+slug,
            "note":"编辑质量检查并非搜索引擎排名预测；公开前仍需人工核验图片与引用授权。"}


# V56 · Lightweight read-only audit of the *published* catalog.
# Checks are editorial hints, never ranking predictions or evidence of
# real crawler indexing. Drafts and private user content are not inspected.
_KIND_MAP={"site":("sites","websites"),"module":("modules","sections"),
           "pattern":("patterns","patterns"),"article":("articles","insights")}


def audit_resource(kind,slug,item,catalog):
    """Evaluate source, SEO text, image context and published cross-references."""
    from app import seo_routes
    issues=[]
    if not isinstance(item,dict):
        return {"kind":kind,"slug":slug,"title":slug,"issues":[
            {"code":"invalid","label":"内容结构无效","advice":"请检查公开内容的数据结构。","priority":"high"}],
            "issue_count":1,"high_issue_count":1,"priority":"high"}
    title=item.get("seo_title") or item.get("name") or item.get("title") or ""
    description=(item.get("seo_description") or
                 (item.get("summary") or item.get("focus") if kind=="site" else
                  item.get("lesson") or item.get("summary") if kind=="module" else
                  item.get("question") or item.get("principle") if kind=="pattern" else
                  item.get("subtitle")) or "")
    title=str(title).strip()
    description=str(description).strip()
    def warn(code,label,advice):
        urgent=(code in ("source","broken_refs","sources") or
                (code in ("title","description") and label.startswith("缺少")) or
                (code=="links" and label=="缺少已发布的参考模块"))
        issues.append({"code":code,"label":label,"advice":advice,
                       "priority":"high" if urgent else "normal"})
    if not title:
        warn("title","缺少标题","补全内容标题或 SEO 标题。")
    elif len(title)>70:
        warn("title","搜索标题较长","建议缩短标题，避免搜索结果截断。")
    if not description:
        warn("description","缺少搜索描述","填写具体的研究摘要或 SEO 描述。")
    elif len(description)<35:
        warn("description","搜索描述过短","说明研究对象、设计特点与可借鉴的价值。")
    elif len(description)>170:
        warn("description","搜索描述较长","建议提炼内容重点，避免展示截断。")
    cover=seo_routes.content_image(_KIND_MAP[kind][1],item,catalog)
    if kind in ("site","module","article") and not cover:
        warn("image","内容封面待补充","添加真实案例截图或已授权的媒体封面。")
    if kind=="site":
        url=item.get("url","")
        if not isinstance(url,str) or not url.startswith(("https://","http://")):
            warn("source","原始网站来源不完整","补充可访问的官方来源 URL。")
        related=[x for x in catalog["modules"].values()
                 if isinstance(x,dict) and x.get("site_id")==slug]
        if not related:
            warn("links","尚无关联页面模块","适当关联该网站的首屏、产品页或其他真实页面模块。")
        if isinstance(item.get("gallery"),list):
            if any(isinstance(x,dict) and x.get("url") and not str(x.get("label") or "").strip()
                   for x in item["gallery"]):
                warn("image_labels","部分截图缺少说明","为案例相册的图片补充名称与上下文。")
    elif kind=="module":
        site=item.get("site_id")
        if not isinstance(site,str) or site not in catalog["sites"]:
            warn("source","所属网站来源不可用","关联已经发布的网站案例。")
        if not isinstance(item.get("url"),str) or not item["url"].startswith(("https://","http://")):
            warn("source_url","缺少原始页面链接","尽量提供对应模块的官网页面 URL，便于核实。")
        linked=any(slug in p.get("modules",[]) for p in catalog["patterns"].values()
                   if isinstance(p,dict) and isinstance(p.get("modules"),list))
        if not linked:
            warn("links","尚未关联设计模式","如适合，关联解释该模块方法的设计模式。")
    elif kind=="pattern":
        mods=item.get("modules")
        if not isinstance(mods,list) or not any(
                isinstance(mid,str) and mid in catalog["modules"] for mid in mods):
            warn("links","缺少已发布的参考模块","关联至少一个实际页面模块来支撑设计原则。")
        if not str(item.get("when") or "").strip():
            warn("context","尚未说明适用场景","补充这种设计方法适合解决什么问题。")
    elif kind=="article":
        if not str(item.get("published_at") or "").strip():
            warn("date","缺少文章发布日期","填写可核实的发布日期，帮助读者判断研究时效。")
        references=item.get("references")
        target_kind={"website":"sites","module":"modules","pattern":"patterns","article":"articles"}
        valid_refs=0
        broken_refs=0
        for ref in references if isinstance(references,list) else []:
            if (not isinstance(ref,(list,tuple)) or len(ref)<2 or
                not isinstance(ref[0],str) or not isinstance(ref[1],str)):
                broken_refs+=1
                continue
            target=target_kind.get(ref[0])
            if target and ref[1] in catalog[target]:
                valid_refs+=1
            else:
                broken_refs+=1
        if broken_refs:
            warn("broken_refs",str(broken_refs)+" 条引用无法对应公开内容",
                 "重新选择已发布的案例、模块、模式或文章，避免无效内链。")
        has_external=any(
            isinstance(block,dict) and block.get("type")=="link"
            and isinstance(block.get("url"),str) and block["url"].startswith(("https://","http://"))
            for section in (item.get("sections") if isinstance(item.get("sections"),list) else [])
            if isinstance(section,dict)
            for block in (section.get("blocks") if isinstance(section.get("blocks"),list) else []))
        if not valid_refs and not has_external:
            warn("sources","没有有效的公开参考来源","加入已发布的案例、模块或可核实的原始资料链接。")
        missing_alt=0
        for section in (item.get("sections") if isinstance(item.get("sections"),list) else []):
            if not isinstance(section,dict):continue
            blocks=section.get("blocks")
            if isinstance(blocks,list):
                missing_alt+=sum(1 for b in blocks if isinstance(b,dict) and
                    b.get("type")=="image" and b.get("src") and
                    not str(b.get("alt") or "").strip())
            elif section.get("image") and not str(section.get("image_caption") or "").strip():
                missing_alt+=1
        if missing_alt:
            warn("alt",str(missing_alt)+" 张正文配图缺少 ALT",
                 "为配图写明具体内容；旧版章节图片可补充说明或转换为独立图片块。")
    urgent=sum(x["priority"]=="high" for x in issues)
    return {"kind":kind,"slug":slug,"title":title or slug,
            "issues":issues,"issue_count":len(issues),
            "high_issue_count":urgent,"priority":"high" if urgent else "normal"}


def audit_published(kind,catalog,limit=100):
    """Summarize all public resources; return at most limit records needing edits."""
    key,route=_KIND_MAP[kind]
    records=catalog.get(key,{})
    findings=[]
    for slug,item in records.items():
        if not isinstance(slug,str):continue
        result=audit_resource(kind,slug,item,catalog)
        if result["issue_count"]:findings.append(result)
    findings.sort(key=lambda x:(x["priority"]!="high",-x["high_issue_count"],-x["issue_count"],x["slug"]))
    count=len(findings)
    return {"kind":kind,"route":route,"total":len(records),
            "flagged":count,"high":sum(x["priority"]=="high" for x in findings),
            "clear":max(0,len(records)-count),
            "items":findings[:limit],"remaining":max(0,count-limit),
            "note":"仅检查已公开内容的文本、图片和关联完整性；不检测外链是否在线，也不代表搜索排名或收录状态。"}

def register_quality_routes(app:FastAPI):
    @app.get("/api/admin/seo/audit",include_in_schema=False)
    def audit_catalog(request:Request,kind:cms_routes.KIND="site"):
        cms_routes.require_admin(request,permission="view")
        return audit_published(kind,cms_routes.seo_routes.catalog())

    @app.post("/api/admin/seo/check",include_in_schema=False)
    def check_draft(data:SeoPreview,request:Request):
        cms_routes.require_admin(request,permission="edit")
        payload=cms_routes.cleaned("article",data.slug,data.payload)
        return quality_report(data.slug,payload)
    @app.get("/api/admin/seo/article/{slug}",include_in_schema=False)
    def read_check(slug:str,request:Request):
        cms_routes.require_admin(request,permission="view")
        if not cms_routes.SLUG.fullmatch(slug):user_auth.error(422,"文章 ID 无效。")
        entry=cms_routes.cms_item("article",slug,{"user_id":"cms"})
        return quality_report(slug,entry["payload"])
