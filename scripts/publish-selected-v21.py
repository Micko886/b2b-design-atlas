#!/usr/bin/env python3
"""Promote only visual-reviewed company and deep-page screenshots from staged V2.1."""
import json,re,datetime,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
config=json.loads(Path(sys.argv[2]).read_text())
original=json.loads(Path(sys.argv[3]).read_text())
audit=json.loads((root/'screenshots/research-v21/audit.json').read_text())
approved=set(audit['accepted_sites'])
selected=set(config['include_sites'])
assert len(selected)>=7 and selected<=approved,("bad approved sites",selected-approved)
new_site_ids={x['id'] for x in original['sites']}
assert len(new_site_ids)==15 and selected<=new_site_ids
accepted_deep={x['id'] for x in audit['audits'] if x['kind']=='inner-page' and x['status']=='captured'}
selected_deep=set(config['include_deep_pages'])
assert len(selected_deep)>=8 and selected_deep<=accepted_deep,("bad approved inner pages",selected_deep-accepted_deep)
existing_catalog=json.loads((root/'app/source_index.json').read_text())
existing_modules=json.loads((root/'app/module_catalog.json').read_text())
new_metadata={x['id']:x for x in existing_catalog['sites'] if x['id'] in new_site_ids}
if len(new_metadata)<len(selected):raise ValueError('Missing metadata for reviewed websites')
keep=set(selected_deep)
for m in existing_modules:
 if m['site_id'] in selected and m['id'] in {m['site_id']+'-hero',m['site_id']+'-detail'}:
  keep.add(m['id'])
# Only previously-existing (not newly captured) modules and manually approved new screenshots.
new_id_set=set(audit['accepted_module_ids'])
pruned_modules=[m for m in existing_modules if m['id'] not in new_id_set or m['id'] in keep]
pruned_notes=[n for n in existing_catalog['notes'] if n['id'] not in new_id_set or n['id'] in keep]
selected_sites=[]
for sid in config['include_sites']:
 s=new_metadata[sid]
 s['curation_batch']='v21'
 s['visual_style']=config.get('notes',{}).get(sid,{}).get('style','Distinctive real B2B design')
 s['design_strengths']=config.get('notes',{}).get(sid,{}).get('strengths',[])
 s['reviewed_for_design']=True
 for path in [root/'screenshots/sites'/f'{sid}.webp',root/'screenshots/modules'/f'{sid}-hero.webp']:
  assert path.exists(),path
 selected_sites.append(s)
existing_catalog['sites']=selected_sites+[s for s in existing_catalog['sites'] if s['id'] not in new_site_ids]
existing_catalog['notes']=pruned_notes
existing_catalog['checked_at']=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
(root/'app/source_index.json').write_text(json.dumps(existing_catalog,ensure_ascii=False,indent=2)+'\n')
(root/'app/module_catalog.json').write_text(json.dumps(pruned_modules,ensure_ascii=False,indent=2)+'\n')
# Keep fresh hand-approved homepage images in the front portfolio.
path=root/'static/assets/atlas-v10.js'
js=path.read_text()
m=re.search(r"const curated=\[[^\]]*\](?=\.map\(id=>state\.sites\.find)",js)
assert m is not None,'Cannot locate curated website array'
old=re.findall(r"'([^']+)'",m.group())
top=config['home_features']
assert set(top)<=selected
ids=list(dict.fromkeys(top+old))
js=js[:m.start()]+'const curated=['+','.join(repr(x) for x in ids)+']'+js[m.end():]
path.write_text(js)
summary={
 'source':'real browser screenshots from official B2B company sites',
 'review_batch':'v21',
 'website_candidates':audit['sites_attempted'],
 'website_browser_verified':audit['sites_captured'],
 'websites_visually_approved':len(selected),
 'new_websites':config['include_sites'],
 'inner_pages_attempted':audit['inner_attempted'],
 'inner_pages_browser_verified':audit['inner_captured'],
 'inner_pages_visually_approved':len(selected_deep),
 'new_sections':sum(m['id'] in new_id_set for m in pruned_modules),
 'all_modules_count':len(pruned_modules),
 'all_site_metadata_count':len(existing_catalog['sites']),
 'pattern_groups_target':20,
 'excluded_capture_sites':sorted(approved-selected),
 'excluded_deep_pages':sorted(accepted_deep-selected_deep)
}
(root/'CURATION-V21.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print('PROMOTE_V21',json.dumps(summary,ensure_ascii=False),flush=True)
