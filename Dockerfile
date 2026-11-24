FROM python:3.12-slim
WORKDIR /srv/atlas
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ATLAS_DB_PATH=/srv/atlas/data/atlas.sqlite3 ATLAS_REMOTE_CAPTURE_FALLBACK=0
COPY atlas-source-v23.tar.gz /tmp/atlas-source.tar.gz
RUN tar -xzf /tmp/atlas-source.tar.gz -C /srv/atlas && rm /tmp/atlas-source.tar.gz
COPY screenshots/ /srv/atlas/screenshots/
COPY enhancements/atlas-research.js /srv/atlas/static/assets/atlas-research.js
COPY enhancements/atlas-research.css /srv/atlas/static/assets/atlas-research.css
RUN python -c "from pathlib import Path; p=Path('static/index.html'); s=p.read_text(); assert '</head>' in s; p.write_text(s.replace('</head>', '<link rel=\"stylesheet\" href=\"/assets/atlas-research.css?v=24\"><script defer src=\"/assets/atlas-research.js?v=24\"></script></head>'))"
RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /srv/atlas/data
RUN python create_module_catalog.py
EXPOSE 8000
CMD ["python","run.py"]
