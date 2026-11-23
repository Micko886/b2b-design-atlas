from pathlib import Path
p=Path("/srv/atlas/static/assets/atlas-v09.js")
s=p.read_text()
old="state.sites=(data.sites||[]).filter(x=>x.screenshot_url).map(x=>({...x,isPage:false}));"
new="state.sites=(data.sites||[]).filter(x=>x.screenshot_url&&!['molex','festo'].includes(x.id)).map(x=>({...x,isPage:false}));"
if old not in s:
    raise SystemExit("Expected V0.9 site list filter not found")
p.write_text(s.replace(old,new))
