# B2B Atlas · Visual Research Library

A curated library of real B2B websites, page sections, and design patterns. Explore actual screenshots, research design decisions, study source-checked project profiles, and save reference briefs.

## Frontend: clean rebuild

The application now uses **one HTML shell, one CSS design system, and one JavaScript entrypoint**, all under `frontend/`. Historic V24–V36 layered frontend scripts were removed and are not loaded.

- `frontend/index.html` — semantic document, header, overlay and SPA entry.
- `frontend/app.css` — unified responsive design language, white background and electric blue accents.
- `frontend/app.js` — homepage, site and section galleries, pattern studies, research profiles, saved references and project board.
- `frontend/research.json` — five reviewed research profiles (including Vast and Fictiv).
- `frontend/patterns.json` — 20 curated design patterns.

The Docker build preserves the existing Python API and source-attributed screenshots. It replaces the old frontend directly instead of adding another CSS or JS override. Screenshot color palettes are generated from existing image files.

## UX / Design

Home: a compact branded hero and real website preview stack, with search and featured cases.

Websites and Sections: full-width native-ratio masonry gallery, filter bar, compact metadata and three-color swatches. No duplicate navigation sidebar.

Detail: actual source screenshots with a thumbnail gallery, project attributes, color/typography evidence, design breakdowns and linked sections and patterns.

Patterns: independent educational examples tied to actual section captures. Board and saved items are kept in the browser's local storage.

## Release checks

Review desktop (1440px), tablet (768px) and mobile (390px) for layout overflow, real image loading, category and style filters, search, screenshot switching, source links, patterns, saved items, board notes, export and keyboard access.

See `frontend/README.md` for the design contract.
