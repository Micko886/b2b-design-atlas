#!/usr/bin/env python3
"""Replace Patterns presentation only, preserving its 20 studies and source links."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'static/assets/atlas-v10.js'
s=p.read_text()
a=s.index('function patterns(){')
b=s.index('function empty(',a)
new=r"""
function patterns(){
 const cards=PATTERN_STUDIES_V21;
 const families=PATTERN_FAMILIES_V21;
 const tabs=['All patterns',...families];
 return `<main class="wrap pt-library" aria-label="Design pattern library">
  <header class="pt-heading"><div><h1>Patterns</h1><p>Explore how real B2B websites solve the same design problems.</p></div><span class="pt-total">${cards.length} patterns <span>·</span> ${families.length} categories</span></header>
  <div class="pt-toolbar"><nav class="pt-filters" aria-label="Filter patterns">${tabs.map((f,i)=>`<button type="button" class="pt-filter" data-pt-filter="${i}" aria-pressed="${i===0}">${escapeHTML(f)} <small>${i===0?cards.length:cards.filter(c=>c.family===f).length}</small></button>`).join('')}</nav></div>
  <div class="pt-results"><span data-pt-count aria-live="polite">${cards.length} patterns</span><span>Real website comparisons</span></div>
  <div class="pt-grid">${cards.map(s=>{
    const examples=s.modules.map(id=>state.modules.find(m=>m.id===id)).filter(Boolean);
    return `<article class="pt-card" data-pt-family="${families.indexOf(s.family)+1}" id="pattern-${escapeHTML(s.id)}">
      <div class="pt-card-head"><span class="pt-category">${escapeHTML(s.family)}</span><h2>${escapeHTML(s.title)}</h2><p>${escapeHTML(s.question)}</p></div>
      <div class="pt-comparison">${examples.slice(0,2).map((m,i)=>`<a class="pt-example" href="${moduleHref(m.id)}" data-link="${moduleHref(m.id)}">
        <div class="pt-image">${capture(m)}</div>
        <div class="pt-caption"><span class="pt-source-name notranslate" translate="no">${escapeHTML(owner(m)?.name||'Source')}</span>${svg('arrow')}</div>
      </a>`).join('')}</div>
      <div class="pt-card-foot"><p>${escapeHTML(s.principle)}</p>
        <details class="pt-notes"><summary>Design notes <span>${svg('right')}</span></summary>
          <div class="pt-notes-body"><strong>What to compare</strong><p>${escapeHTML(s.compare)}</p><strong>When to use it</strong><p>${escapeHTML(s.when)}</p>
            ${examples.length>2?`<a class="pt-more" href="${moduleHref(examples[2].id)}" data-link="${moduleHref(examples[2].id)}">Related example: ${escapeHTML(owner(examples[2])?.name||'Source')} ${svg('arrow')}</a>`:''}
          </div>
        </details>
      </div>
    </article>`;
  }).join('')}</div>
 </main>`;
}
document.addEventListener('click',function(e){
 const btn=e.target.closest('[data-pt-filter]');
 if(!btn)return;
 const library=btn.closest('.pt-library');
 if(!library)return;
 const selected=btn.dataset.ptFilter;
 library.querySelectorAll('[data-pt-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===btn)));
 let visible=0;
 library.querySelectorAll('.pt-card').forEach(card=>{const show=selected==='0'||card.dataset.ptFamily===selected;card.hidden=!show;if(show)visible++});
 library.querySelector('[data-pt-count]').textContent=visible+' patterns';
});
"""
s=s[:a]+new+'\n'+s[b:]
p.write_text(s)
p=root/'static/assets/atlas-v10.css'
css=p.read_text()
# Remove the obsolete page-specific V2.1 rules rather than stacking competing overrides.
marker='/* B2B Atlas V2.1 — 20 source-linked design Patterns'
if marker in css:css=css[:css.index(marker)].rstrip()+'\n'
css+=r"""
/* Patterns V2.2: compact image-first library, scoped styles, no screenshot cropping. */
.pt-library{padding:39px 0 80px;color:#171717}
.pt-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;padding-bottom:24px}
.pt-heading h1{font-size:clamp(32px,3vw,43px);letter-spacing:-.055em;line-height:1.12;margin:0 0 7px;font-weight:730}
.pt-heading p{font-size:14px;line-height:1.5;color:#727272;margin:0}
.pt-total{font-size:12px;color:#666;font-weight:500;white-space:nowrap;padding-bottom:3px}
.pt-total>span{color:#bbb;margin:0 4px}
.pt-toolbar{border-top:1px solid #e9e9e9;border-bottom:1px solid #e9e9e9;padding:12px 0}
.pt-filters{display:flex;gap:7px;overflow:auto;scrollbar-width:none}
.pt-filter{font:inherit;display:inline-flex;align-items:center;gap:6px;white-space:nowrap;flex:none;border:1px solid #e5e5e5;border-radius:7px;padding:9px 12px;background:#fff;color:#444;font-size:12px;line-height:18px;cursor:pointer;font-weight:550}
.pt-filter small{font-size:10px;font-weight:500;color:#8b8b8b}
.pt-filter:hover{background:#f5f5f5}
.pt-filter[aria-pressed=true]{background:#181818;border-color:#181818;color:white}
.pt-filter[aria-pressed=true] small{color:#bbb}
.pt-filter:focus-visible,.pt-example:focus-visible,.pt-notes summary:focus-visible{outline:2px solid #777;outline-offset:3px}
.pt-results{display:flex;justify-content:space-between;align-items:center;padding:18px 0 13px;font-size:12px;color:#777}
.pt-results>span:first-child{font-weight:620;color:#444}
.pt-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;align-items:start}
.pt-card{background:#fff;border:1px solid #e6e6e6;border-radius:12px;overflow:hidden;min-width:0;display:flex;flex-direction:column}
.pt-card[hidden]{display:none!important}
.pt-card-head{padding:18px 18px 15px;min-height:109px}
.pt-category{font-size:10px;color:#777;font-weight:620}
.pt-card-head h2{font-size:21px;line-height:1.2;letter-spacing:-.035em;margin:6px 0 6px;font-weight:680}
.pt-card-head p{color:#666;font-size:12px;line-height:1.55;margin:0;max-width:550px}
.pt-comparison{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;padding:0 12px}
.pt-example{display:block;min-width:0;overflow:hidden;text-decoration:none!important;color:inherit;background:#f3f3f3;border:1px solid #e9e9e9;border-radius:7px}
.pt-image{aspect-ratio:1.9;display:flex;align-items:center;justify-content:center;overflow:hidden;background:#f0f0f0}
.pt-image img{display:block!important;width:100%!important;height:100%!important;max-width:100%!important;max-height:100%!important;object-fit:contain!important;object-position:center!important;transition:none!important;transform:none!important}
.pt-caption{background:#fff;padding:9px 10px;display:flex;align-items:center;gap:8px;justify-content:space-between;border-top:1px solid #e9e9e9;min-height:34px}
.pt-source-name{font-size:11px;font-weight:630;white-space:nowrap;text-overflow:ellipsis;overflow:hidden}
.pt-caption svg{width:12px;height:12px;flex:none;color:#777}
.pt-example:hover .pt-caption{background:#f7f7f7}
.pt-card-foot{padding:14px 18px 0}
.pt-card-foot>p{font-size:12px;line-height:1.55;color:#555;margin:0 0 12px;min-height:37px}
.pt-notes{border-top:1px solid #eee}
.pt-notes summary{display:flex;justify-content:space-between;align-items:center;list-style:none;cursor:pointer;font-size:12px;font-weight:620;padding:12px 0;color:#353535}
.pt-notes summary::-webkit-details-marker{display:none}
.pt-notes summary svg{width:13px;height:13px;transition:transform .15s}
.pt-notes[open] summary svg{transform:rotate(90deg)}
.pt-notes-body{font-size:12px;line-height:1.6;color:#666;padding:0 0 15px}
.pt-notes-body strong{font-size:11px;color:#222}
.pt-notes-body p{margin:4px 0 12px}
.pt-more{display:inline-flex;gap:6px;align-items:center;font-weight:600;color:#333}
.pt-more svg{width:12px;height:12px}
@media(max-width:950px){.pt-grid{grid-template-columns:1fr}.pt-card-head{min-height:0}.pt-card-foot>p{min-height:0}.pt-heading{align-items:flex-start}}
@media(max-width:600px){.pt-library{padding:25px 0 55px}.pt-heading{display:block;padding-bottom:17px}.pt-heading h1{font-size:34px}.pt-heading p{font-size:13px}.pt-total{display:block;margin-top:12px}.pt-toolbar{padding:9px 0}.pt-filter{padding:7px 10px}.pt-grid{gap:13px}.pt-results{font-size:11px;padding:14px 0 10px}.pt-card-head{padding:14px 13px 12px}.pt-card-head h2{font-size:19px}.pt-comparison{padding:0 8px;gap:7px}.pt-card-foot{padding:12px 13px 0}.pt-caption{padding:8px 7px}.pt-source-name{font-size:10px}}
@media(max-width:380px){.pt-comparison{grid-template-columns:1fr}.pt-image{aspect-ratio:1.9}}
"""
p.write_text(css)
print('PATTERNS_V22_APPLIED',len(s),len(css))
