FROM python:3.12-slim
WORKDIR /srv/atlas
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ATLAS_DB_PATH=/srv/atlas/data/atlas.sqlite3 ATLAS_REMOTE_CAPTURE_FALLBACK=0
COPY atlas-source-v23.tar.gz /tmp/atlas-source.tar.gz
RUN tar -xzf /tmp/atlas-source.tar.gz -C /srv/atlas && rm /tmp/atlas-source.tar.gz
COPY screenshots/ /srv/atlas/screenshots/
COPY enhancements/atlas-research.js /srv/atlas/static/assets/atlas-research.js
COPY enhancements/atlas-research.css /srv/atlas/static/assets/atlas-research.css
COPY enhancements/atlas-next.js /srv/atlas/static/assets/atlas-next.js
COPY enhancements/atlas-next.css /srv/atlas/static/assets/atlas-next.css
COPY enhancements/build_palettes.py /srv/atlas/build_palettes.py
COPY enhancements/atlas-v31.js /srv/atlas/static/assets/atlas-v31.js
COPY enhancements/atlas-v31.css /srv/atlas/static/assets/atlas-v31.css
COPY enhancements/atlas-v32.js /srv/atlas/static/assets/atlas-v32.js
COPY enhancements/atlas-v32.css /srv/atlas/static/assets/atlas-v32.css
COPY enhancements/atlas-v33.js /srv/atlas/static/assets/atlas-v33.js
COPY enhancements/atlas-v33.css /srv/atlas/static/assets/atlas-v33.css
RUN python -c "from pathlib import Path; p=Path('static/index.html'); s=p.read_text(); assert '</head>' in s; p.write_text(s.replace('</head>', '<link rel=\"stylesheet\" href=\"/assets/atlas-research.css?v=30\"><script defer src=\"/assets/atlas-research.js?v=30\"></script><link rel=\"stylesheet\" href=\"/assets/atlas-next.css?v=30\"><script defer src=\"/assets/atlas-next.js?v=30\"></script><link rel=\"stylesheet\" href=\"/assets/atlas-v31.css?v=31.1\"><script defer src=\"/assets/atlas-v31.js?v=31\"></script><link rel=\"stylesheet\" href=\"/assets/atlas-v32.css?v=32\"><script defer src=\"/assets/atlas-v32.js?v=32\"></script><link rel=\"stylesheet\" href=\"/assets/atlas-v33.css?v=33\"><script defer src=\"/assets/atlas-v33.js?v=33\"></script></head>'))"
RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /srv/atlas/data
RUN python create_module_catalog.py && python build_palettes.py
EXPOSE 8000
CMD ["python","run.py"]
