from pathlib import Path
p = Path("/srv/atlas/static/assets/atlas-v05.js")
s = p.read_text(encoding="utf-8")
old = "pick.filter(s=>!featured.includes(s)).slice(0,3).concat(featured.slice(0,3)).slice(0,6)"
new = "pick.filter(s=>!featured.includes(s)).slice(0,6)"
if old not in s:
    raise SystemExit("Duplicate archive gallery patch target missing")
s = s.replace(old, new)
old_loading = """loading="${priority?'eager':'lazy'}" """
if old_loading not in s:
    raise SystemExit("Image loading patch target missing")
s = s.replace(old_loading, """loading="eager" """)
p.write_text(s, encoding="utf-8")
print("V0.5 gallery quality patches applied")
