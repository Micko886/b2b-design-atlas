#!/usr/bin/env python3
"""Publish only visually reviewed B2B Atlas V2.0 references, never all captured candidates.

python publish-curated-v20.py /path/to/extracted/atlas /repo/curation-v20.json
"""
from pathlib import Path
import json,re,sys,datetime

root=Path(sys.argv[1]).resolve()
manifest=json.loads(Path(sys.argv[2]).read_text())
audit=json.loads((root/'screenshots/research-v20/audit.json').read_text())
selected=manifest['include']
if not 12<=len(selected)<=29:raise SystemExit('Manual curation must include 12-29 reviewed websites')
if len(set(selected))!=len(selected):raise SystemExit('Duplicate manual review ids')
if not set(selected)<=set(audit['approved']):raise SystemExit('Manual review contains sites not captured successfully')
d_path=root/'app/source_index.json'
m_path=root/'app/module_catalog.json'
catalog=json.loads(d_path.read_text())
modules=json.loads(m_path.read_text())
batch=set(audit['approved'])
sites={x['id']:x for x in catalog['sites']}
reviewed=[]
for sid in selected:
    if sid not in sites:raise SystemExit('Missing site metadata: '+sid)
    x=sites[sid]
    values=manifest.get('notes',{}).get(sid,{})
    x['visual_style']=values.get('style','Distinctive B2B design')
    x['design_strengths']=values.get('strengths',[])
    x['curation_batch']='v20'
    x['reviewed_for_design']=True
    # Original source can be audited; never synthesize or recolor a screenshot.
    for family,filename in [('sites',sid+'.webp'),('notes',sid+'-hero.webp'),('modules',sid+'-hero.webp')]:
        if not (root/'screenshots'/family/filename).is_file():
            raise SystemExit(f'Missing authentic {family} screenshot for {sid}')
    reviewed.append(x)
prior=[x for x in catalog['sites'] if x['id'] not in batch]
catalog['sites']=reviewed+prior
catalog['notes']=[n for n in catalog['notes'] if n['site_id'] not in batch or n['site_id'] in selected]
prior_modules=[m for m in modules if m['site_id'] not in batch]
new_modules=[m for m in modules if m['site_id'] in selected]
modules=new_modules+prior_modules
if len(new_modules)<len(selected):raise SystemExit('Some accepted sites have no real sections')
assert len({m['id'] for m in modules})==len(modules)
catalog['checked_at']=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
d_path.write_text(json.dumps(catalog,indent=2,ensure_ascii=False)+'\n')
m_path.write_text(json.dumps(modules,indent=2,ensure_ascii=False)+'\n')
script=root/'static/assets/atlas-v10.js'
content=script.read_text()
match=re.search(r"const curated=\[[^\]]*\](?=\.map\(id=>state\.sites\.find)",content)
if not match:raise SystemExit('Cannot locate current homepage curated array')
old=re.findall(r"'([^']+)'",match.group())
preferred=manifest['home_features']
if not set(preferred)<=set(selected):raise SystemExit('Homepage features not approved')
ids=list(dict.fromkeys(preferred+old))
content=content[:match.start()]+"const curated=["+','.join(repr(x) for x in ids)+"]"+content[match.end():]
script.write_text(content)
summary=dict(review_batch='v20',explored=audit['attempted'],
    browser_captured=audit['accepted'],manually_approved=len(selected),
    excluded_after_visual_review=list(sorted(batch-set(selected))),
    new_modules=len(new_modules),new_sites=selected,
    total_metadata_sites=len(catalog['sites']),total_sections=len(modules))
(root/'CURATION-V20.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print('CURATED_V20',json.dumps(summary,ensure_ascii=False),flush=True)
