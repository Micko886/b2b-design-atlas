# B2B Atlas · V1.7 real masonry galleries

Global B2B website inspiration directory using actual source-attributed company screenshots.

## Actual waterfall layout

- **Websites:** CSS multi-column masonry (not Grid), with independently stacked columns and varied image-preview aspect ratios.
- **Sections:** independently stacked columns sized to the real crop's native aspect ratio, without imposing artificial image heights.
- **Breakpoints:** 3 columns desktop, 2 tablet, 1 mobile; compact mode 4 / 3 / 2.
- **Spacing:** 18px horizontal and 22px vertical on desktop, no manual margin-top offsets or shared-grid-row gaps.
- **Order:** column-major (top to bottom in each column); this is a flowing, responsive CSS column layout.
- **Source images:** original screenshots remain available in case details and original source sites are linked. The gallery can crop the preview for visual rhythm.

## Verified

GitHub Actions Chromium QA (V1.7) passed on Websites and Sections at desktop, tablet, and mobile sizes, including independent column positions, adjacent card gaps, image loads and no horizontal overflow.

Production source: `atlas-source-v17.tar.gz` — the Docker image unpacks this archive and copies the tracked `screenshots/` folder.

Screenshots are for source-attributed visual study, not third-party code redistribution.
