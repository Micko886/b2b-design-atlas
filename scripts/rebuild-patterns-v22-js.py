#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'static/assets/atlas-v10.js'
js=p.read_text()
assert 'const PATTERN_STUDIES_V21=' in js
start=js.index('function patterns(){')
end=js.index('function empty(',start)
new=r"""
function patterns(){
return §<div class="wrap p22" id="p22-top">
<header class="p22-hero">
  <div><span class="p22-eyebrow">B2B DESIGN LIBRARY / 03</span><h1>Patterns<span>.</span></h1><p>One design problem, different real-world solutions.<br>Compare what makes each layout work.</p></div>
  <div class="p22-counter"><strong>20</strong><span>curated comparisons<br>5 collections</span></div>
</header>
<div class="p22-nav"><b>Browse by purpose</b><nav aria-label="Pattern categories">
¤{PATTERN_FAMILIES_V21.map((f,i)=>§<a href="#p22-category-¤{i}">¤{escapeHTML(f)}</a>§).join('')}
</nav></div>
¤{PATTERN_FAMILIES_V21.map((family,i)=>{
 const studies=PATTERN_STUDIES_V21.filter(x=>x.family===family);
 return §<section class="p22-group" id="p22-category-¤{i}">
 <header class="p22-group-head"><div><span>0¤{i+1}</span><h2>¤{escapeHTML(family)}</h2></div><small>¤{studies.length} design patterns</small></header>
 <div class="p22-grid">
 ¤{studies.map((s,j)=>{
  const examples=s.modules.map(id=>state.modules.find(x=>x.id===id)).filter(Boolean);
  return §<article class="p22-card">
   <div class="p22-card-top"><span>¤{String(i*4+j+1).padStart(2,'0')} / ¤{escapeHTML(family)}</span><span>REAL SOURCES</span></div>
   <div class="p22-compare">
    ¤{examples.slice(0,2).map(m=>§<a href="¤{moduleHref(m.id)}" data-link="¤{moduleHref(m.id)}" class="p22-source">
     <div class="p22-image">¤{capture(m)}</div>
     <div class="p22-caption"><span><b class="notranslate" translate="no">¤{escapeHTML(owner(m)?.name||'Website')}</b><small>¤{escapeHTML(m.title)}</small></span>¤{svg('arrow')}</div>
    </a>§).join('')}
   </div>
   <div class="p22-copy"><h3>¤{escapeHTML(s.title)}</h3><p>¤{escapeHTML(s.question)}</p></div>
   <details class="p22-details"><summary>Design notes <span>¤{svg('right')}</span></summary>
    <div><b>Approach</b><p>¤{escapeHTML(s.principle)}</p><b>What to compare</b><p>¤{escapeHTML(s.compare)}</p><b>Best used for</b><p>¤{escapeHTML(s.when)}</p>
     ¤{examples[2]?§<a href="¤{moduleHref(examples[2].id)}" data-link="¤{moduleHref(examples[2].id)}">Third example: ¤{escapeHTML(owner(examples[2])?.name||'Website')} ¤{svg('right')}</a>§:''}
    </div>
   </details>
  </article>§;
 }).join('')}
 </div></section>§;
}).join('')}
</div>§;
}
"""
new=new.replace('§',chr(96)).replace('¤{',chr(36)+'{')
js=js[:start]+new+'\n'+js[end:]
p.write_text(js)
print('PATTERNS_V22_JS',len(js))
