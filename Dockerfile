FROM python:3.12-slim
WORKDIR /srv/atlas
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ATLAS_DB_PATH=/srv/atlas/data/atlas.sqlite3 ATLAS_REMOTE_CAPTURE_FALLBACK=0
COPY atlas-source-v08.b64 /tmp/atlas-source.b64
RUN base64 -d /tmp/atlas-source.b64 | tar -xz -C /srv/atlas && rm /tmp/atlas-source.b64
COPY screenshots/ /srv/atlas/screenshots/
RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /srv/atlas/data
RUN python create_module_catalog.py
RUN printf '%s\n' '@media(max-width:820px){.v8-sidebar{display:block;border-top:1px solid #e1e4dd;border-bottom:1px solid #e1e4dd;padding-bottom:10px;margin-bottom:5px}.v8-sidebar-head{padding:9px 0;border-bottom:0}.v8-sidebar-group{margin:0;padding:2px 0 8px;border:0}.v8-sidebar-group>p{font-size:10px;margin:5px 0 7px}.v8-facet-list{display:flex;flex-direction:row;flex-wrap:nowrap;gap:6px;overflow-x:auto;scrollbar-width:thin;padding-bottom:6px}.v8-facet{white-space:nowrap;flex:0 0 auto;gap:6px;border:1px solid #dfe4db;padding:7px 10px;font-size:11px;background:#fff}.v8-facet.is-active{background:#30483e;border-color:#30483e;color:#fff}.v8-facet.is-active em{color:#e1e9df}.v8-sidebar-foot{display:none}}' >> /srv/atlas/static/assets/atlas-v08.css
EXPOSE 8000
CMD ["python","run.py"]
