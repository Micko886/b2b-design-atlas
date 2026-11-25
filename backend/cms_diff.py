"""V51.18 · Auditable content comparison for reviewers and editors.

Line-based diff is intentionally limited for browser rendering and has no
script/HTML output; the frontend is responsible for HTML escaping.
"""
from __future__ import annotations
from difflib import SequenceMatcher
from fastapi import FastAPI,Request
from app import cms_routes,user_auth

def content_lines(kind,payload):
    if not isinstance(payload,dict):return []
    if kind!="article":
        result=[]
        for key in sorted(payload):
            if key in ("id",):continue
            value=payload[key]
            if isinstance(value,(str,int,float,bool)):
                result.append(key+"  ·  "+str(value))
            elif isinstance(value,list):
                result.append(key+"  ·  "+", ".join(map(str,value[:15]))[:250])
        return result[:180]
    lines=[]
    for key in ("title","subtitle","seo_title","seo_description","author","category"):
        if payload.get(key):lines.append(key+"  ·  "+str(payload[key]))
    for i,section in enumerate(payload.get("sections",[])[:40],1):
        if not isinstance(section,dict):continue
        lines.append("章节 "+str(i)+"  ·  "+str(section.get("title","")))
        if isinstance(section.get("blocks"),list):
            for block in section["blocks"][:70]:
                if not isinstance(block,dict):continue
                t=block.get("type","")
                if t=="list":text=" · ".join(str(x) for x in block.get("items",[]))
                elif t=="table":text=" | ".join(" / ".join(str(x) for x in row)
                                                   for row in block.get("rows",[]) if isinstance(row,list))
                elif t=="image":text=str(block.get("src",""))+" · "+str(block.get("alt",""))+" · "+str(block.get("caption",""))
                elif t=="link":text=str(block.get("text",""))+" · "+str(block.get("url",""))
                else:text=str(block.get("text",""))
                lines.append(t+"  ·  "+text)
        else:
            for p in section.get("paragraphs",[]):lines.append("正文  ·  "+str(p))
            for p in section.get("bullets",[]):lines.append("要点  ·  "+str(p))
            if section.get("callout"):lines.append("提示  ·  "+str(section["callout"]))
            if section.get("image"):lines.append("图片  ·  "+str(section["image"]))
    return [text[:450] for text in lines[:230]]

def compare_payloads(kind,baseline,current):
    before=content_lines(kind,baseline)
    after=content_lines(kind,current)
    differ=SequenceMatcher(a=before,b=after,autojunk=False)
    chunks=[]
    for tag,i,j,k,l in differ.get_opcodes():
        if tag=="equal" and j-i>4:
            # Show context around changed sections, not hundreds of identical lines.
            chunks.append({"tag":"equal","before":before[i:i+2],
                           "after":after[k:k+2],"collapsed":j-i-4})
            chunks.append({"tag":"equal","before":before[j-2:j],
                           "after":after[l-2:l],"collapsed":0})
        else:
            chunks.append({"tag":tag,"before":before[i:j],"after":after[k:l],"collapsed":0})
    changed=[key for key in sorted(set(baseline or {})|set(current or {}))
             if key!="id" and (baseline or {}).get(key)!=(current or {}).get(key)]
    return {"changed_fields":changed,"chunks":chunks[:120],
            "summary":{"before_lines":len(before),"after_lines":len(after),
                       "added":sum(len(c["after"]) for c in chunks if c["tag"] in ("insert","replace")),
                       "removed":sum(len(c["before"]) for c in chunks if c["tag"] in ("delete","replace"))}}

def register_diff_routes(app:FastAPI):
    @app.get("/api/admin/content/{kind}/{slug}/diff",include_in_schema=False)
    def compare(kind:cms_routes.KIND,slug:str,request:Request,revision:int=0):
        cms_routes.require_admin(request,permission="view")
        cms_routes.ensure_cms()
        with user_auth.db() as db:
            row=db.one("SELECT * FROM atlas_cms_entries WHERE kind=? AND slug=?",(kind,slug))
            revisions=db.all("""SELECT revision,action,created_at FROM atlas_cms_history
                              WHERE kind=? AND slug=? ORDER BY revision DESC LIMIT 30""",(kind,slug))
            old=None
            if revision:
                chosen=db.one("""SELECT snapshot_json FROM atlas_cms_history
                                  WHERE kind=? AND slug=? AND revision=?""",(kind,slug,revision))
                if not chosen:user_auth.error(404,"对比版本不存在。")
                old=cms_routes.parse_json(chosen["snapshot_json"])
        source=cms_routes.base_item(kind,slug)
        if not row and not source:user_auth.error(404,"内容不存在。")
        current=cms_routes.parse_json(row["draft_json"]) if row else source
        if not revision:
            old=cms_routes.parse_json(row["published_json"]) if row and row["published_json"] else source or {}
        result=compare_payloads(kind,old or {},current or {})
        result.update({"kind":kind,"slug":slug,"current_revision":row["revision"] if row else 0,
                       "baseline_revision":revision or "published",
                       "baseline_label":("历史 v"+str(revision)) if revision else "当前公开版本",
                       "revisions":revisions})
        return result
