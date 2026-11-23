# B2B Atlas · v1.6 reviewed gallery
Global B2B website inspiration directory.

- **Websites:** 3-column balanced gallery on large screens; no masonry-like row gaps.
- **Sections:** genuine cropped screenshots, fit inside their visual frame rather than aggressively cropped.
- **Patterns:** real examples compared in horizontal rows without labels covering images.
- **Source of truth:** deployed screenshots/ in this repository contain authentic captures. The app archive intentionally excludes local placeholder screenshots and takes those assets from this folder.
- **Deployment:** Dockerfile extracts atlas-source-v16.b64 into /srv/atlas and copies the screenshots directory as a separate tracked asset tree.
- **Production caveat:** free Render storage is ephemeral and no rights to republish third-party screenshots are implied.

Run locally by unpacking atlas-source-v16.b64 (base64 -d | tar -xz) and installing requirements.txt. For the same images as production, also copy the tracked screenshots folder from this repository.
