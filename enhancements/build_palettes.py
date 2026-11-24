from pathlib import Path
from PIL import Image
from collections import defaultdict
import json, math
out={}
for f in Path('screenshots').rglob('*'):
    if f.suffix.lower() not in ('.webp','.png','.jpg','.jpeg'): continue
    try:
        im=Image.open(f).convert('RGB')
        im.thumbnail((96,96))
        bins=defaultdict(list)
        for rgb in im.getdata(): bins[tuple(x//32 for x in rgb)].append(rgb)
        ranked=[tuple(round(sum(v[i] for v in b)/len(b)) for i in range(3)) for b in sorted(bins.values(),key=len,reverse=True)]
        colors=[]
        for rgb in ranked:
            if all(math.dist(rgb,c)>=65 for c in colors): colors.append(rgb)
            if len(colors)==3: break
        for rgb in ranked:
            if len(colors)==3: break
            if rgb not in colors: colors.append(rgb)
        out['/'+f.as_posix()]=['#%02X%02X%02X'%c for c in colors]
    except (OSError, ValueError): continue
Path('static/assets/screenshot-palettes.json').write_text(json.dumps(out,separators=(',',':')))
print('Screenshot palettes:',len(out))
