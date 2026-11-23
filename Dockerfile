FROM python:3.12-slim
WORKDIR /srv/atlas
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ATLAS_DB_PATH=/srv/atlas/data/atlas.sqlite3
RUN apt-get update && apt-get install -y --no-install-recommends xz-utils && rm -rf /var/lib/apt/lists/*
COPY atlas-source.tar.xz /tmp/atlas-source.tar.xz
RUN tar -xJf /tmp/atlas-source.tar.xz -C /srv/atlas && rm /tmp/atlas-source.tar.xz
RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /srv/atlas/data
EXPOSE 8000
CMD ["python","run.py"]
