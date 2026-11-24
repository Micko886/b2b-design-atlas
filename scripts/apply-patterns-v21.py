#!/usr/bin/env python3
"""Upgrade source-attributed Patterns to 20 actual comparisons, no fake examples."""
from pathlib import Path
import json,re,sys
root=Path(sys.argv[1]).resolve()
catalog_path=Path(sys.argv[2]).resolve()
data=json.loads(catalog_path.read_text())
patterns=data['patterns']
families=data['families']
modules=json.loads((root/'app/module_catalog.json').read_text())
source_sites=json.loads((root/'app/source_index.json').read_text())['sites']
module_by_id={m['id']:m for m in modules}
sites={x['id']:x for x in source_sites}
assert len(patterns)==20
assert len({x['id'] for x in patterns})==len(patterns)
assert len(families)==5
for p in patterns:
 assert p['family'] in families,p
 assert len(p['modules'])>=2,p['id']
 selected=[module_by_id.get(mid) for mid in p['modules']]
 if not all(selected):raise RuntimeError('Pattern references missing a real module: '+p['id']+': '+str(p['modules']))
 if len({x['site_id'] for x in selected})<2:raise RuntimeError('Pattern must compare two different real websites: '+p['id'])
 for m in selected:
  assert m['site_id'] in sites,('Missing source site',m['id'])
  assert (root/'screenshots/modules'/m['image_file']).exists(),('Missing image',m['id'])
  assert m['url'].startswith('https://'),('Missing source URL',m['id'])
(root/'app/pattern_catalog.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
js_path=root/'static/assets/atlas-v10.js'
js=js_path.read_text()
start=js.index('function patterns(){')
end=js.index('function empty(',start)
new=r"""
const PATTERN_STUDIES_V21=__PATTERN_DATA__;
const PATTERN_FAMILIES_V21=__PATTERN_FAMILIES__;
function patterns(){
  return `<div class="wrap patterns-v21">
    <header class="patterns-hero-v21">
      <div><span>CURATED DESIGN PATTERNS</span><h1>Study the thinking.<br><em>Not the template.</em></h1></div>
      <div class="patterns-summary-v21"><strong>20</strong><span>grounded design moves<br>5 families · real B2B source pages</span><p>Each comparison pairs original page captures and explains what problem the layout solves, how to inspect it, and when it is useful.</p></div>
    </header>
    <nav class="patterns-nav-v21" aria-label="Pattern categories">
      ${PATTERN_FAMILIES_V21.map((fam,i)=>`<a href="#pattern-family-${i}"><span>0${i+1}</span>${escapeHTML(fam)}</a>`).join('')}
    </nav>
    ${PATTERN_FAMILIES_V21.map((family,i)=>{
      const studies=PATTERN_STUDIES_V21.filter(x=>x.family===family);
      return `<section class="pattern-family-v21" id="pattern-family-${i}">
        <div class="pattern-family-heading-v21"><span>${String(i+1).padStart(2,'0')} / RESEARCH SERIES</span><h2>${escapeHTML(family)}</h2><p>${studies.length} real visual decisions</p></div>
        <div class="pattern-studies-v21">${studies.map((s,j)=>{
          const examples=s.modules.map(id=>state.modules.find(m=>m.id===id)).filter(Boolean);
          return `<article class="pattern-study-v21" id="pattern-${escapeHTML(s.id)}">
            <div class="pattern-study-intro-v21">
              <span class="pattern-index-v21">${String(i*4+j+1).padStart(2,'0')} — ${escapeHTML(s.family)}</span>
              <h3>${escapeHTML(s.title)}</h3>
              <p class="pattern-problem-v21">${escapeHTML(s.question)}</p>
              <p class="pattern-principle-v21">${escapeHTML(s.principle)}</p>
              <details class="pattern-research-v21">
                <summary>What to compare ${svg('right')}</summary>
                <p>${escapeHTML(s.compare)}</p>
                <p><b>Use when:</b> ${escapeHTML(s.when)}</p>
              </details>
            </div>
            <div class="pattern-proof-v21">
              <div class="pattern-pair-v21">${examples.slice(0,2).map((m,k)=>`
                <a class="pattern-source-v21" href="${moduleHref(m.id)}" data-link="${moduleHref(m.id)}">
                  <div class="pattern-source-image-v21">${capture(m)}</div>
                  <div class="pattern-source-caption-v21">
                    <strong class="notranslate" translate="no">${escapeHTML(owner(m)?.name||'Real source')}</strong>
                    <span>${escapeHTML(m.title)}</span>
                    ${svg('arrow')}
                  </div>
                </a>`).join('')}</div>
              ${examples.length>2?`<div class="pattern-third-v21"><span>Also see</span><a href="${moduleHref(examples[2].id)}" data-link="${moduleHref(examples[2].id)}"><b class="notranslate" translate="no">${escapeHTML(owner(examples[2])?.name||'Source')}</b> — ${escapeHTML(examples[2].title)} ${svg('right')}</a></div>`:''}
            </div>
          </article>`;
        }).join('')}</div>
      </section>`;
    }).join('')}
  </div>`;
}
"""
new=new.replace('__PATTERN_DATA__',json.dumps(patterns,ensure_ascii=False,separators=(',',':')))
new=new.replace('__PATTERN_FAMILIES__',json.dumps(families,ensure_ascii=False,separators=(',',':')))
js=js[:start]+new+'\n'+js[end:]
js_path.write_text(js)
css_path=root/'static/assets/atlas-v10.css'
css=css_path.read_text()
css+=r"""

/* B2B Atlas V2.1 — 20 source-linked design Patterns, real two-site comparison. */
.patterns-v21{padding:62px 0 112px;color:#161616}
.patterns-hero-v21{display:grid;grid-template-columns:1.25fr .55fr;gap:70px;align-items:end;padding:0 0 44px;border-bottom:1px solid #e8e8eb}
.patterns-hero-v21>div:first-child>span,.pattern-family-heading-v21>span,.pattern-index-v21{font-size:10px;color:#85858a;letter-spacing:.14em;font-weight:800}
.patterns-hero-v21 h1{font-size:clamp(45px,5.2vw,84px);line-height:.98;letter-spacing:-.07em;margin:17px 0 0;font-weight:780}
.patterns-hero-v21 h1 em{font-style:normal;color:#8a8a90}
.patterns-summary-v21{display:grid;grid-template-columns:auto 1fr;gap:8px 16px;align-items:center}
.patterns-summary-v21 strong{font-size:62px;line-height:1;letter-spacing:-.065em}
.patterns-summary-v21 span{font-size:12px;line-height:1.5;font-weight:650;color:#4e4e53}
.patterns-summary-v21 p{grid-column:span 2;margin:8px 0 0;font-size:12px;line-height:1.6;color:#77777c;max-width:340px}
.patterns-nav-v21{display:flex;gap:7px;overflow-x:auto;scrollbar-width:none;padding:18px 0 20px;border-bottom:1px solid #ededed}
.patterns-nav-v21>a{white-space:nowrap;padding:10px 15px;border:1px solid #e5e5e7;border-radius:100px;font-weight:680;font-size:11px;color:#303034;background:#fff}
.patterns-nav-v21>a:hover{background:#171717;color:#fff;border-color:#171717}
.patterns-nav-v21 span{font-size:9px;margin-right:9px;color:#aaa}
.pattern-family-v21{scroll-margin-top:90px;padding-top:70px}
.pattern-family-heading-v21{display:flex;align-items:baseline;gap:24px;padding-bottom:24px;border-bottom:1px solid #eee}
.pattern-family-heading-v21>span{min-width:168px}
.pattern-family-heading-v21 h2{font-size:32px;line-height:1.1;letter-spacing:-.055em;margin:0}
.pattern-family-heading-v21>p{margin-left:auto;font-size:11px;color:#929297}
.pattern-studies-v21{display:block}
.pattern-study-v21{display:grid;grid-template-columns:minmax(270px,.75fr) minmax(0,1.35fr);gap:6%;padding:42px 0;border-bottom:1px solid #e9e9eb}
.pattern-study-intro-v21 h3{font-size:clamp(23px,2.1vw,34px);line-height:1.1;letter-spacing:-.055em;margin:14px 0}
.pattern-problem-v21{max-width:410px;font-size:14px;line-height:1.55;color:#404044;font-weight:630;margin:0 0 11px}
.pattern-principle-v21{max-width:420px;font-size:12px;line-height:1.7;color:#86868c;margin:0}
.pattern-research-v21{max-width:410px;margin-top:23px;border-top:1px solid #ebebed;padding-top:14px}
.pattern-research-v21 summary{cursor:pointer;font-weight:650;display:flex;align-items:center;gap:8px;font-size:11px;color:#333;list-style:none}
.pattern-research-v21 summary::-webkit-details-marker{display:none}
.pattern-research-v21 summary .ic{height:13px;width:13px}
.pattern-research-v21 p{font-size:12px;line-height:1.6;color:#68686e;margin:10px 0}
.pattern-pair-v21{display:grid;grid-template-columns:1fr 1fr;gap:13px}
.pattern-source-v21{display:block;min-width:0;overflow:hidden;border:1px solid #e6e6e8;border-radius:13px;background:#fff;transition:transform .2s ease,box-shadow .2s ease}
.pattern-source-v21:hover{transform:translateY(-3px);box-shadow:0 12px 27px rgba(0,0,0,.07)}
.pattern-source-image-v21{aspect-ratio:1.32;overflow:hidden;background:#f5f5f6}
.pattern-source-image-v21 img{width:100%;height:100%;display:block;object-fit:cover;object-position:top}
.pattern-source-caption-v21{padding:12px 13px 14px;display:grid;grid-template-columns:1fr auto;gap:4px}
.pattern-source-caption-v21 strong{grid-column:1;font-size:12px;line-height:1.3;color:#171717}
.pattern-source-caption-v21 span{grid-column:1;font-size:10px;color:#8a8a8f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pattern-source-caption-v21 .ic{grid-column:2;grid-row:1/3;width:14px;height:14px;color:#555;align-self:center}
.pattern-third-v21{display:flex;gap:12px;align-items:baseline;padding:11px 2px}
.pattern-third-v21 span{font-size:10px;color:#aaa;text-transform:uppercase;letter-spacing:.09em}
.pattern-third-v21>a{font-size:11px;color:#69696f;display:flex;align-items:center;gap:5px}
.pattern-third-v21>a b{color:#333}
.pattern-third-v21 .ic{width:12px;height:12px}
@media(max-width:1000px){
 .patterns-hero-v21{grid-template-columns:1fr .6fr;gap:26px}
 .pattern-study-v21{grid-template-columns:1fr;gap:22px}
 .pattern-family-heading-v21>span{min-width:unset}
}
@media(max-width:680px){
 .patterns-v21{padding:37px 0 75px}
 .patterns-hero-v21{grid-template-columns:1fr;gap:24px}
 .patterns-hero-v21 h1{font-size:48px}
 .patterns-summary-v21{max-width:330px}
 .patterns-summary-v21 strong{font-size:48px}
 .pattern-family-v21{padding-top:45px;scroll-margin-top:70px}
 .pattern-family-heading-v21{display:block}
 .pattern-family-heading-v21 h2{font-size:28px;margin:9px 0}
 .pattern-family-heading-v21>p{font-size:11px;margin:0}
 .pattern-study-v21{padding:25px 0 29px}
 .pattern-study-intro-v21 h3{font-size:27px}
 .pattern-pair-v21{gap:8px}
 .pattern-source-image-v21{aspect-ratio:1.18}
 .pattern-source-caption-v21{padding:9px 8px 11px}
 .pattern-source-caption-v21 strong{font-size:10px}
 .pattern-source-caption-v21 span{font-size:9px}
}
"""
css_path.write_text(css)
print('APPLIED_PATTERNS_V21',len(patterns),len(families),sum(len(p['modules']) for p in patterns),len(js))
