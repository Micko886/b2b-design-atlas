# B2B Atlas — Clean Frontend

This is the only actively loaded UI. No historical atlas-vXX CSS or JavaScript is loaded.

## Architecture
- \`index.html\`: document shell, accessible navigation, overlay and main region.
- \`app.css\`: unified design system, components and responsive breakpoints.
- \`app.js\`: discovery, filters, masonry cards, research dossiers, patterns, saved collection and project board.
- \`research.json\`: source-reviewed company/design research (5 profiles); unknown fields are not guessed.
- \`patterns.json\`: 20 design patterns tied to real curated modules.

## Data contracts
Live backend: \`/api/source-library\` and \`/api/module-library\`.
Generated screenshot color index: \`/assets/screenshot-palettes.json\`.
Local saved references and project notes remain browser-local in localStorage.

## Design contract
- Home: brand overview, three real website captures, search, featured discovery.
- Websites / Sections: full-width gallery, horizontal category navigation, small controls and original-ratio masonry images. Never a duplicate sidebar/module navigation.
- Project detail: big source capture with thumbnails on the left, verified attributes and visual data on the right, followed by concrete design analysis and related references.
- Patterns: problem, principle and actual section evidence; no fabricated metrics.
- System: white background, near-black text, blue \`#0647FF\`, modern sans-serif typography, subdued chrome, accessible focus rings and responsive layout.
- Preservation: original image URLs, data provenance, valid source links and existing saved/board localStorage keys.

## Release gate
Review 390px, 768px, and 1440px viewports. Check no horizontal overflow, no script exceptions, intact thumbnails, search, category/style/color filters, save / board persistence, notes, export and pattern deep links. Only replace production on a complete QA pass.
