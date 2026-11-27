"""V68: XML RSS for publicly approved B2B Atlas research articles."""
from __future__ import annotations

import re
from datetime import datetime,timezone
from xml.etree import ElementTree as ET

ATOM="http://www.w3.org/2005/Atom"
ET.register_namespace("atom",ATOM)


def xml_text(value,limit=600):
    # XML 1.0 disallows certain control characters even when escaped.
    text=str(value or "")[:limit]
    return "".join(char for char in text if ord(char) in (9,10,13) or
                   32<=ord(char)<=0xD7FF or 0xE000<=ord(char)<=0xFFFD or
                   0x10000<=ord(char)<=0x10FFFF)


def build(catalog,origin):
    """Generate RSS only from the already-published catalog snapshot."""
    from app import seo_routes
    origin=origin.rstrip("/")
    root=ET.Element("rss",{"version":"2.0"})
    channel=ET.SubElement(root,"channel")
    ET.SubElement(channel,"title").text="B2B Atlas · 研究文章"
    ET.SubElement(channel,"link").text=origin+"/insights"
    ET.SubElement(channel,"description").text="B2B 网站、页面模块与设计方法的公开研究文章。"
    ET.SubElement(channel,"language").text="zh-CN"
    ET.SubElement(channel,"{"+ATOM+"}link",{"href":origin+"/feed.xml",
                                       "rel":"self","type":"application/rss+xml"})
    entries=catalog.get("articles",{}) if isinstance(catalog,dict) else {}
    if not isinstance(entries,dict):entries={}
    ordered=sorted(entries.items(),
                   key=lambda pair:(str(pair[1].get("published_at") or "") if isinstance(pair[1],dict) else "",
                                    str(pair[0])),reverse=True)
    count=0
    for slug,article in ordered:
        if count>=30:break
        if not isinstance(slug,str) or not seo_routes._SLUG.fullmatch(slug):
            continue
        if not isinstance(article,dict):continue
        title=xml_text(article.get("title"),200).strip()
        if not title:continue
        url=origin+"/insights/"+slug
        entry=ET.SubElement(channel,"item")
        ET.SubElement(entry,"title").text=title
        ET.SubElement(entry,"link").text=url
        ET.SubElement(entry,"guid",{"isPermaLink":"true"}).text=url
        summary=article.get("seo_description") or article.get("subtitle") or ""
        ET.SubElement(entry,"description").text=xml_text(summary)
        date=seo_routes.valid_date(article.get("published_at"))
        if date:
            # RSS mandates a timestamp; midnight UTC represents the stored
            # calendar date, not a claimed exact publication hour.
            stamp=datetime.strptime(date,"%Y-%m-%d").replace(tzinfo=timezone.utc)
            ET.SubElement(entry,"pubDate").text=stamp.strftime("%a, %d %b %Y 00:00:00 GMT")
        count+=1
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)
