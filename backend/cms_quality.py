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

def register_quality_routes(app:FastAPI):
    @app.post("/api/admin/content/seo/check",include_in_schema=False)
    def check_draft(data:SeoPreview,request:Request):
        cms_routes.require_admin(request,permission="edit")
        payload=cms_routes.cleaned("article",data.slug,data.payload)
        return quality_report(data.slug,payload)
    @app.get("/api/admin/content/{slug}/seo",include_in_schema=False)
    def read_check(slug:str,request:Request):
        cms_routes.require_admin(request,permission="view")
        if not cms_routes.SLUG.fullmatch(slug):user_auth.error(422,"文章 ID 无效。")
        entry=cms_routes.cms_item("article",slug,{"user_id":"cms"})
        return quality_report(slug,entry["payload"])
