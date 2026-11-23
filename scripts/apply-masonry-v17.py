#!/usr/bin/env python3
"""V1.7: actual CSS multicolumn masonry, not a CSS grid or faux stagger."""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
css_file = root / "static/assets/atlas-v10.css"
if not css_file.is_file():
    raise SystemExit("Missing v16 CSS: " + str(css_file))
css = css_file.read_text(encoding="utf-8")
css += r"""

/* V1.7 — actual MASONRY. Columns flow independently; no shared Grid rows.
   Site screenshots use varied viewport crops (full capture available on detail).
   Section captures retain their real natural aspect ratios.
   Browser reading order is top-to-bottom within each column. */
.v13-website-wall,
.v13-section-wall {
    display:block!important;
    column-count:3!important;
    column-gap:18px!important;
    column-fill:balance!important;
}
.v13-website-wall > .site-tile,
.v13-website-wall > .site-tile:nth-child(n),
.v13-section-wall > .module-tile,
.v13-section-wall > .module-tile:nth-child(n) {
    display:block!important;
    width:100%!important;
    max-width:100%!important;
    margin:0 0 22px!important;
    padding:0;
    grid-column:auto!important;
    grid-row:auto!important;
    break-inside:avoid!important;
    -webkit-column-break-inside:avoid!important;
    page-break-inside:avoid!important;
    vertical-align:top;
}
.v13-website-wall .site-card .site-image {
    height:auto!important;
    aspect-ratio:1.56!important;
    overflow:hidden;
}
.v13-website-wall .site-card:nth-child(6n + 1) .site-image,
.v13-website-wall > .site-card:nth-child(6n + 1) .site-image {aspect-ratio:1.30!important}
.v13-website-wall > .site-card:nth-child(6n + 3) .site-image {aspect-ratio:1.78!important}
.v13-website-wall > .site-card:nth-child(6n + 4) .site-image {aspect-ratio:1.40!important}
.v13-website-wall > .site-card:nth-child(6n + 6) .site-image {aspect-ratio:1.68!important}
.v13-website-wall .site-image img {
    width:100%!important;
    height:100%!important;
    object-fit:cover!important;
    object-position:left top!important;
}
.v13-section-wall .module-card .module-picture {
    aspect-ratio:auto!important;
    height:auto!important;
    overflow:hidden;
}
.v13-section-wall .module-card .module-picture>a {
    display:block!important;
    height:auto!important;
}
.v13-section-wall .module-card .module-picture img {
    display:block!important;
    width:100%!important;
    height:auto!important;
    object-fit:contain!important;
    object-position:top left;
}
.v13-website-wall.is-compact,
.v13-section-wall.is-compact {
    column-count:4!important;
    column-gap:14px!important;
}
.v13-website-wall.is-compact > .site-tile,
.v13-section-wall.is-compact > .module-tile {margin-bottom:15px!important}
@media(max-width:1180px){
  .v13-website-wall,.v13-section-wall {column-count:2!important;column-gap:16px!important}
  .v13-website-wall.is-compact,.v13-section-wall.is-compact {column-count:3!important}
}
@media(max-width:680px){
  .v13-website-wall,.v13-section-wall {column-count:1!important}
  .v13-website-wall.is-compact,.v13-section-wall.is-compact {column-count:2!important;column-gap:10px!important}
  .v13-website-wall > .site-tile,
  .v13-section-wall > .module-tile {margin-bottom:18px!important}
}
"""
css_file.write_text(css,encoding="utf-8")
print("Applied real masonry to",css_file,"bytes",len(css))
