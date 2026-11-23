from pathlib import Path
import re

root=Path("/srv/atlas/static/assets")
js_path=root/"atlas-v10.js"
css_path=root/"atlas-v10.css"
js=js_path.read_text()

CARD=r'''function websiteCard(item,{index=0,featured=false}={}){const siteDomain=domain(item);return `<article class="site-tile site-card ${featured?'site-tile--featured':''}">
  <div class="site-image site-card-media"><a class="site-card-cover" href="${siteHref(item.id)}" data-link="${siteHref(item.id)}" aria-label="Explore ${escapeHTML(item.name)}">${capture(item,{priority:index<5})}</a><div class="shot-actions site-card-actions">${saveBtn(item)}<button class="shot-preview" data-preview="${escapeHTML(keyFor(item))}" aria-label="Quick preview ${escapeHTML(item.name)}" title="Quick preview">${svg('maximize')}</button></div></div>
  <div class="site-tile-footer site-card-body">
    <div class="site-card-kicker"><span class="tile-domain notranslate" translate="no">${escapeHTML(siteDomain)}</span><span class="site-card-separator">/</span><span>${escapeHTML(item.sector)}</span></div>
    <div class="site-card-title-row"><a href="${siteHref(item.id)}" data-link="${siteHref(item.id)}" class="tile-name notranslate" translate="no">${escapeHTML(item.name)}</a><a href="${escapeHTML(item.url)}" target="_blank" rel="noopener noreferrer" class="site-card-visit" aria-label="Visit ${escapeHTML(item.name)} website"><span>Visit site</span>${svg('arrow')}</a></div>
    <p class="site-card-focus">${escapeHTML(item.focus)}</p>
  </div>
 </article>`}'''
js,n=re.subn(r"function websiteCard\(item,\{index=0,featured=false\}=\{\}\)\{.*?(?=function moduleCard)",CARD,js,flags=re.S)
if n!=1:
    raise SystemExit(f"V1.4 website card patch mismatch: {n}")

js=js.replace('<span class="v13-shot-glass"><b>${escapeHTML(item.name)}</b><small>${escapeHTML(item.sector)}</small></span>','<span class="v13-shot-glass"><b class="notranslate" translate="no">${escapeHTML(item.name)}</b><small>${escapeHTML(item.sector)}</small></span>')
js_path.write_text(js)

css=css_path.read_text()
CARD_CSS=r'''
/* V1.4 / WEBSITE CARD REFINEMENT */
.site-card{min-width:0;background:#fff;border:1px solid #ececee;border-radius:18px;padding:8px 8px 0;overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,.025);transition:transform .28s var(--ease),box-shadow .28s var(--ease),border-color .28s var(--ease)}
.site-card:hover{transform:translateY(-3px);border-color:#dcdce0;box-shadow:0 18px 46px rgba(0,0,0,.085)}
.site-card .site-image{aspect-ratio:1.58;border:0;border-radius:12px;background:#f4f4f5;box-shadow:none;transform:none!important}
.site-card:hover .site-image{box-shadow:none;transform:none!important}
.site-card .site-image>a{border-radius:12px}
.site-card .site-image img{transition:transform .45s var(--ease),filter .3s var(--ease)}
.site-card:hover .site-image img{transform:scale(1.012)}
.site-card-actions{top:10px;right:10px;gap:6px}
.site-card-actions button{width:32px;height:32px;border-radius:9px;border:1px solid rgba(0,0,0,.075);background:rgba(255,255,255,.92);color:#111;box-shadow:0 4px 14px rgba(0,0,0,.07);backdrop-filter:blur(18px) saturate(160%)}
.site-card-actions button:hover{background:#111;color:#fff;border-color:#111}
.site-card-actions .saved{background:#111!important;color:#fff!important;border-color:#111!important}
.site-card-actions .shot-preview{opacity:0;transform:translateY(3px) scale(.96);pointer-events:none}
.site-card:hover .shot-preview,.site-card .shot-preview:focus-visible{opacity:1;transform:none;pointer-events:auto}
.site-card-body{display:block;padding:14px 10px 16px;min-height:94px}
.site-card-kicker{display:flex;align-items:center;gap:7px;min-width:0;color:#8d8d93;font-size:9px;line-height:1.2;letter-spacing:.015em;margin-bottom:7px;white-space:nowrap;overflow:hidden}
.site-card-kicker>span{overflow:hidden;text-overflow:ellipsis}
.site-card-kicker .tile-domain{margin:0;color:#6e6e73;font-size:9px;font-weight:600;flex:0 1 auto}
.site-card-separator{color:#c8c8cc;flex:0 0 auto!important}
.site-card-title-row{display:flex;align-items:center;justify-content:space-between;gap:14px}
.site-card .tile-name{display:block;min-width:0;color:#111;font-size:16px;line-height:1.2;font-weight:720;letter-spacing:-.35px;text-decoration:none!important;transition:opacity .18s ease}
.site-card .tile-name:hover{opacity:.62}
.site-card-focus{margin:5px 0 0!important;color:#7f7f85!important;font-size:10.5px!important;line-height:1.4!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.site-card-visit{display:inline-flex;align-items:center;gap:5px;flex:0 0 auto;color:#6e6e73;font-size:10px;font-weight:650;opacity:0;transform:translateX(-3px);transition:opacity .18s ease,transform .18s ease,color .18s ease}
.site-card-visit .ic{width:13px;height:13px}
.site-card:hover .site-card-visit,.site-card-visit:focus-visible{opacity:1;transform:none}
.site-card-visit:hover{color:#111}
.site-tile--featured.site-card{border-radius:20px;padding:9px 9px 0}
.site-tile--featured.site-card .site-image{border-radius:13px}
.site-tile--featured.site-card .site-card-body{padding:16px 12px 18px;min-height:102px}
.site-tile--featured.site-card .tile-name{font-size:18px;letter-spacing:-.48px}
.site-card .tile-source{display:none!important}
@media(hover:none){.site-card-visit{opacity:1;transform:none}.site-card-actions .shot-preview{display:none}}
@media(max-width:650px){.site-card{padding:6px 6px 0;border-radius:15px}.site-card .site-image{border-radius:10px}.site-card-body{padding:11px 8px 13px;min-height:84px}.site-card-kicker{margin-bottom:6px;font-size:8.5px}.site-card .tile-name,.site-tile--featured.site-card .tile-name{font-size:15px}.site-card-focus{font-size:10px!important}.site-card-visit span{display:none}.site-card-visit .ic{width:14px;height:14px}.site-card-actions{top:8px;right:8px}.site-card-actions button{width:30px;height:30px;border-radius:8px}}
'''
if "V1.4 / WEBSITE CARD REFINEMENT" not in css:
    css_path.write_text(css+"\n"+CARD_CSS)

print("Applied V1.4 website-card refinement")
