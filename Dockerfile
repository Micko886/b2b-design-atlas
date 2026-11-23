FROM python:3.12-slim
WORKDIR /srv/atlas
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ATLAS_DB_PATH=/srv/atlas/data/atlas.sqlite3
COPY atlas-source-v05.b64 /tmp/atlas-source.b64
RUN base64 -d /tmp/atlas-source.b64 | tar -xz -C /srv/atlas && rm /tmp/atlas-source.b64
COPY screenshots/ /srv/atlas/screenshots/
RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /srv/atlas/data
EXPOSE 8000
CMD ["python","run.py"]
