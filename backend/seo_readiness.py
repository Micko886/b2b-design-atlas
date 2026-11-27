"""V73: technical SEO/GEO launch preflight for the *current published* site.

No remote claims: domain DNS, Google/Bing ownership, crawl and indexing
must be verified in their respective platforms after the real domain is bound.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from urllib.parse import urlsplit

from fastapi import FastAPI, Request

from app import cms_routes, seo_routes

SITEMAP_NS="{http://www.sitemaps.org/schemas/sitemap/0.9}"
MAX_EXAMPLES=14
PRIVATE_PATHS=("/admin","/api/admin","/account","/collections",
               "/board","/login","/register","/forgot-password",
               "/reset-password","/compare")


def valid_origin(origin):
    """Only a single HTTPS origin without credentials, URL path or query."""
    try:
        u=urlsplit(origin)
        return bool(u.scheme=="https" and u.hostname and u.netloc and
                    not u.username and not u.password and
                    u.port in (None,443) and not u.path and not u.query and
                    not u.fragment and " " not in origin and
                    u.hostname==u.hostname.lower() and
                    re.fullmatch(r"[a-z0-9.-]+",u.hostname))
    except ValueError:
        return False


def schema_canonical(schema,canonical):
    """Require a URL anchor for the page, not merely a source citation URL."""
    if not isinstance(schema,dict) or schema.get("@context")!="https://schema.org":
        return False
    nodes=schema.get("@graph") or [schema]
    if not isinstance(nodes,list):return False
    return any(isinstance(node,dict) and
               (node.get("url")==canonical or node.get("mainEntityOfPage")==canonical)
               for node in nodes)


def build_report(collection):
    """Check the same sitemap, robots, JSON-LD and llms data used in HTTP."""
    checks=[]
    errors=[]
    def add(code,title,status,detail,action=""):
        checks.append({"code":code,"title":title,"status":status,
                       "detail":detail,"action":action})
    def failure(code,path,detail):
        errors.append({"code":code,"path":str(path)[:240],
                       "detail":str(detail)[:220]})

    origin=seo_routes.ORIGIN
    origin_valid=valid_origin(origin)
    if not origin_valid:
        add("origin","Canonical 主域名","fail",
            "ATLAS_PUBLIC_ORIGIN 不符合单一 HTTPS 主域名格式。",
            "将 ATLAS_PUBLIC_ORIGIN 设置为 https://正式域名（不包含路径或结尾斜杠），重新部署。")
    elif (not os.getenv("ATLAS_PUBLIC_ORIGIN","").strip() or
          ".onrender.com" in urlsplit(origin).hostname):
        add("origin","Canonical 主域名","pending",
            "目前仍使用 Render 预览域名作为 Canonical，不代表正式域名已绑定。",
            "确认最终域名，完成 DNS/HTTPS/Render 绑定后设置 ATLAS_PUBLIC_ORIGIN，重新部署并复查。")
    else:
        add("origin","Canonical 主域名","pass",
            "已配置自定义 HTTPS Canonical："+origin+"。此项不验证外部 DNS 或 HTTP 重定向。",
            "上线时仍需确认外部访问、HTTPS、旧域名 301 跳转和唯一主域名。")

    robots=seo_routes.robots_document()
    robots_ok=("User-agent: *" in robots and
               "Sitemap: "+origin+"/sitemap.xml" in robots and
               all("Disallow: "+p+"\n" in robots for p in PRIVATE_PATHS) and
               all("Disallow: "+p not in robots for p in
                   ("/websites","/sections","/patterns","/insights","/topics","/directory")))
    add("robots","Robots.txt 公开与私有路径","pass" if robots_ok else "fail",
        "已核对管理员/账户路径排除规则和 Sitemap 指向。" if robots_ok else
        "Robots.txt 的私有路径排除或 Sitemap 地址不一致。",
        "" if robots_ok else "修复 Robots.txt 并保持公开研究路径可抓取。")

    entries=list(seo_routes.sitemap_items(collection))
    paths=[path for path,_ in entries]
    duplicate_count=len(paths)-len(set(paths))
    for path,n in Counter(paths).items():
        if n>1:failure("duplicate_sitemap",path,"重复出现在 Sitemap 中："+str(n)+" 次")
    public_paths=set(paths)
    for path in paths:
        if (not isinstance(path,str) or not path.startswith("/") or
            any(path==private or path.startswith(private+"/") for private in PRIVATE_PATHS)):
            failure("private_sitemap",path,"不应进入 Sitemap 的非公开路径。")
            continue
        try:
            record=seo_routes.seo_record(path,collection)
            if not record or not record.get("indexed") or record.get("path")!=path:
                failure("not_indexable",path,"Sitemap URL 无有效、可索引的公开 SEO 记录。")
                continue
            canonical=origin+path
            schema=seo_routes.seo_schema(
                path,record,collection,canonical,
                origin+(record.get("image") or "/assets/visual-placeholder.svg"))
            if not schema_canonical(schema,canonical):
                failure("schema_canonical",path,"JSON-LD 未与该页面 Canonical URL 对齐。")
        except Exception as exc:
            failure("route_error",path,"公开路由或结构化数据生成失败："+type(exc).__name__)

    try:
        root=ET.fromstring(seo_routes.sitemap_xml(collection))
        locs=[node.text for node in root.iter(SITEMAP_NS+"loc")]
        canonical_urls={origin+path for path in paths}
        xml_ok=(len(locs)==len(paths) and set(locs)==canonical_urls and
                len(locs)==len(set(locs)) and duplicate_count==0)
    except (ET.ParseError,ValueError,TypeError):
        locs=[]
        xml_ok=False
    add("sitemap","XML Sitemap 与 Canonical 一致性",
        "pass" if xml_ok else "fail",
        str(len(locs))+" 个 Sitemap URL，"+str(duplicate_count)+" 个重复；"
        +("与已发布路由一致。" if xml_ok else "存在缺失、重复或 XML 解析错误。"),
        "" if xml_ok else "修复 URL 重复或非公开路径，并重新检查 Sitemap XML。")

    metadata_ok=not errors
    add("metadata","全量公开路由与 Schema 自检",
        "pass" if metadata_ok else "fail",
        "已检查 "+str(len(paths))+" 个 URL 的可索引状态、Canonical 和 JSON-LD；"
        +str(len(errors))+" 处不一致。",
        "" if metadata_ok else "查看下方示例，修复已发布路由后重新执行技术验收。")

    from app import seo_feed
    llms=seo_routes.llms_document(collection)
    links=re.findall(r"\]\((https?://[^)\s]+)\)",llms)
    allowed={origin+path for path in public_paths}|{origin+"/sitemap.xml",origin+"/feed.xml"}
    bad=[link for link in links if link not in allowed]
    try:
        feed=ET.fromstring(seo_feed.build(collection,origin))
        feed_links=[node.text for node in feed.findall("./channel/item/link")]
        bad.extend(link for link in feed_links if link not in allowed)
        feed_valid=True
    except (ET.ParseError,ValueError,TypeError):
        feed_valid=False
    for link in bad[:MAX_EXAMPLES]:failure("discovery_link",link,"AI 导航或 RSS 中存在非 Sitemap 的公开内容链接。")
    discovery_ok=feed_valid and not bad and origin_valid
    add("discovery","GEO 目录与研究 RSS 来源一致性",
        "pass" if discovery_ok else "fail",
        "AI 导航 "+str(len(links))+" 条链接，RSS "+str(len(feed_links) if feed_valid else 0)
        +" 条文章链接；"+str(len(bad))+" 条异常链接。",
        "" if discovery_ok else "修复 llms.txt 或 feed.xml 中无法对应公开资源的链接。")

    platforms=seo_routes.verification_state()
    for provider,label,var in (
            ("google","Google Search Console","ATLAS_GOOGLE_SITE_VERIFICATION"),
            ("bing","Bing Webmaster Tools","ATLAS_BING_SITE_VERIFICATION")):
        state=platforms[provider]
        if state=="configured":
            detail="HTML 所有权验证标签已配置；平台是否通过验证仍需在其控制台确认。"
            action="在对应的站长平台添加正式域名并完成验证后，提交 Sitemap。"
        elif state=="invalid":
            detail="环境变量中的验证字符串未通过安全格式校验，标签不会注入页面。"
            action="使用平台提供的验证 meta 标签 content 值设置 "+var+"，重新部署。"
        else:
            detail="尚未配置 HTML 验证标签；若使用 DNS 验证则无需此标签。"
            action=("在对应站长平台获取验证信息；URL 前缀站点可使用 "+var+
                    "，域名级属性应依平台提示使用 DNS 验证。")
        add("verify_"+provider,label,
            "pass" if state=="configured" else ("fail" if state=="invalid" else "pending"),
            detail,action)

    pending_external=(
        "确认正式域名 DNS 解析、证书与 www/非 www 的唯一主域名及重定向。",
        "在 Google Search Console/Bing 站长平台完成所有权验证，提交正式域名 Sitemap。",
        "上线后使用各平台的 URL 检查工具确认实际抓取、索引和 Schema；本报告不能代替外部验证。"
    )
    counts=dict(Counter(item["status"] for item in checks))
    code_ok=not any(x["status"]=="fail" for x in checks if not x["code"].startswith("verify_"))
    return {
        "origin":origin,"sitemap_url":origin+"/sitemap.xml",
        "inspected_urls":len(paths),"issue_count":len(errors),
        "examples":errors[:MAX_EXAMPLES],"checks":checks,
        "counts":{status:counts.get(status,0) for status in ("pass","pending","fail")},
        "technical_passed":code_ok,
        "external_verification_pending":True,
        "launch_status":"blocked" if not code_ok else
                        ("domain_pending" if any(x["code"]=="origin" and
                                                   x["status"]=="pending" for x in checks)
                         else "external_review"),
        "outside_checks":list(pending_external),
        "note":"这是服务器自身的静态/动态输出一致性检查；不执行外部 DNS/索引查询，不代表搜索平台认可或已收录。"
    }


def register_readiness_routes(app:FastAPI):
    @app.get("/api/admin/seo/readiness",include_in_schema=False)
    def seo_readiness(request:Request):
        cms_routes.require_admin(request,permission="view")
        return build_report(seo_routes.catalog())
