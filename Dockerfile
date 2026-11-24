FROM python:3.12-slim
WORKDIR /srv/atlas
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ATLAS_DB_PATH=/srv/atlas/data/atlas.sqlite3 ATLAS_REMOTE_CAPTURE_FALLBACK=0
# Backend and real captured assets stay intact.
COPY atlas-source-v23.tar.gz /tmp/atlas-source.tar.gz
RUN tar -xzf /tmp/atlas-source.tar.gz -C /srv/atlas && rm /tmp/atlas-source.tar.gz
COPY screenshots/ /srv/atlas/screenshots/
# Remove legacy frontend assets so no old cascade can accidentally load.
RUN find /srv/atlas/static/assets -maxdepth 1 -type f -name "atlas-*.js" -delete \
 && find /srv/atlas/static/assets -maxdepth 1 -type f -name "atlas-*.css" -delete
# One HTML entry, one stylesheet, one app script and two immutable research datasets.
COPY frontend/index.html /srv/atlas/static/index.html
COPY frontend/app.css /srv/atlas/static/assets/app.css
COPY frontend/app.js /srv/atlas/static/assets/app.js
COPY frontend/research.json /srv/atlas/static/assets/research.json
COPY frontend/patterns.json /srv/atlas/static/assets/patterns.json
COPY enhancements/build_palettes.py /srv/atlas/build_palettes.py
RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /srv/atlas/data
RUN python create_module_catalog.py && python build_palettes.py
EXPOSE 8000
CMD ["python","run.py"]
