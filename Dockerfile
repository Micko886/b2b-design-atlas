FROM python:3.12-slim
WORKDIR /srv/atlas
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ATLAS_DB_PATH=/srv/atlas/data/atlas.sqlite3 ATLAS_REMOTE_CAPTURE_FALLBACK=0
COPY atlas-source-v19.tar.gz /tmp/atlas-source.tar.gz
RUN tar -xzf /tmp/atlas-source.tar.gz -C /srv/atlas && rm /tmp/atlas-source.tar.gz
COPY screenshots/ /srv/atlas/screenshots/
RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /srv/atlas/data
RUN python create_module_catalog.py
EXPOSE 8000
CMD ["python","run.py"]
