from pathlib import Path
p=Path("/srv/atlas/static/assets/atlas-v09.js")
s=p.read_text()
old="state.sites=(data.sites||[]).filter(x=>x.screenshot_url).map(x=>({...x,isPage:false}));"
new="state.sites=(data.sites||[]).filter(x=>x.screenshot_url&&!['molex','festo'].includes(x.id)).map(x=>({...x,isPage:false}));"
if old not in s:
    raise SystemExit("Expected V0.9 site list filter not found")
p.write_text(s.replace(old,new))

# Mobile navigation must be collapsed until explicitly opened.
css=Path("/srv/atlas/static/assets/atlas-v09.css")
css.write_text(css.read_text()+"""
@media(max-width:880px){
.main-nav{display:none;position:absolute;top:66px;left:0;right:0;height:auto;margin:0;padding:12px 20px 18px;background:#fff;border-bottom:1px solid #e5e9e9;box-shadow:0 14px 30px rgba(25,43,50,.08);flex-direction:column;align-items:stretch;gap:2px}
.main-nav.open{display:flex}
.main-nav a{height:auto;padding:12px 15px}
}
@media(max-width:600px){.main-nav{top:62px}}
""")
