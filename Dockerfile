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
COPY backend/user_auth.py /srv/atlas/app/user_auth.py
COPY backend/seo_routes.py /srv/atlas/app/seo_routes.py
COPY backend/seo_directory.py /srv/atlas/app/seo_directory.py
COPY backend/seo_methodology.py /srv/atlas/app/seo_methodology.py
COPY backend/seo_feed.py /srv/atlas/app/seo_feed.py
COPY backend/seo_topics.py /srv/atlas/app/seo_topics.py
COPY backend/seo_readiness.py /srv/atlas/app/seo_readiness.py
COPY backend/seo_final_audit.py /srv/atlas/app/seo_final_audit.py
COPY backend/seo_history.py /srv/atlas/app/seo_history.py
COPY backend/admin_routes.py /srv/atlas/app/admin_routes.py
COPY backend/cms_routes.py /srv/atlas/app/cms_routes.py
COPY backend/cms_access.py /srv/atlas/app/cms_access.py
COPY backend/cms_team.py /srv/atlas/app/cms_team.py
COPY backend/cms_schedule.py /srv/atlas/app/cms_schedule.py
COPY backend/cms_diff.py /srv/atlas/app/cms_diff.py
COPY backend/cms_quality.py /srv/atlas/app/cms_quality.py
COPY backend/seo_pages.py /srv/atlas/app/seo_pages.py
COPY backend/analytics_routes.py /srv/atlas/app/analytics_routes.py
COPY backend/analytics_growth.py /srv/atlas/app/analytics_growth.py
COPY backend/install_auth.py /srv/atlas/install_auth.py
RUN python /srv/atlas/install_auth.py
COPY frontend/index.html /srv/atlas/static/index.html
COPY frontend/app.css /srv/atlas/static/assets/app.css
COPY frontend/app.js /srv/atlas/static/assets/app.js
COPY frontend/visual-placeholder.svg /srv/atlas/static/assets/visual-placeholder.svg
COPY frontend/admin.html /srv/atlas/static/admin.html
COPY frontend/admin.css /srv/atlas/static/assets/admin.css
COPY frontend/admin.js /srv/atlas/static/assets/admin.js
COPY frontend/cms.html /srv/atlas/static/cms.html
COPY frontend/cms.css /srv/atlas/static/assets/cms.css
COPY frontend/cms.js /srv/atlas/static/assets/cms.js
COPY frontend/research.json /srv/atlas/static/assets/research.json
COPY frontend/patterns.json /srv/atlas/static/assets/patterns.json
COPY frontend/articles.json /srv/atlas/static/assets/articles.json
COPY enhancements/build_palettes.py /srv/atlas/build_palettes.py
COPY scripts/curate_editorial_v76.py /srv/atlas/curate_editorial_v76.py
RUN pip install --no-cache-dir -r requirements.txt 'psycopg[binary]>=3.2,<4' && mkdir -p /srv/atlas/data
RUN python -m py_compile /srv/atlas/app/seo_topics.py /srv/atlas/curate_editorial_v76.py && python create_module_catalog.py && python build_palettes.py && python curate_editorial_v76.py
# Regression gate: prevent archived public resources from resurfacing in drafts.
COPY scripts/guard_restore.py /srv/atlas/scripts/guard_restore.py
COPY scripts/backup-postgres.sh /srv/atlas/scripts/backup-postgres.sh
COPY scripts/verify-postgres-backup.sh /srv/atlas/scripts/verify-postgres-backup.sh
COPY tests/test_cms_visibility.py /srv/atlas/tests/test_cms_visibility.py
COPY tests/test_restore_guard.py /srv/atlas/tests/test_restore_guard.py
COPY tests/test_admin_guards.py /srv/atlas/tests/test_admin_guards.py
COPY tests/test_cms_v51.py /srv/atlas/tests/test_cms_v51.py
COPY tests/test_cms_taxonomy.py /srv/atlas/tests/test_cms_taxonomy.py
COPY tests/test_analytics.py /srv/atlas/tests/test_analytics.py
COPY tests/test_analytics_growth.py /srv/atlas/tests/test_analytics_growth.py
COPY tests/test_cms_studio_v513.py /srv/atlas/tests/test_cms_studio_v513.py
COPY tests/test_cms_v514.py /srv/atlas/tests/test_cms_v514.py
COPY tests/test_cms_v515.py /srv/atlas/tests/test_cms_v515.py
COPY tests/test_cms_v520.py /srv/atlas/tests/test_cms_v520.py
COPY tests/test_cms_v521.py /srv/atlas/tests/test_cms_v521.py
COPY tests/test_cms_v522.py /srv/atlas/tests/test_cms_v522.py
COPY tests/test_cms_v524.py /srv/atlas/tests/test_cms_v524.py
COPY tests/test_cms_v525.py /srv/atlas/tests/test_cms_v525.py
COPY tests/test_cms_v526.py /srv/atlas/tests/test_cms_v526.py
COPY tests/test_cms_v527.py /srv/atlas/tests/test_cms_v527.py
COPY tests/test_cms_v528.py /srv/atlas/tests/test_cms_v528.py
COPY tests/test_cms_v530.py /srv/atlas/tests/test_cms_v530.py
COPY tests/test_cms_v531.py /srv/atlas/tests/test_cms_v531.py
COPY tests/test_cms_v532.py /srv/atlas/tests/test_cms_v532.py
COPY tests/test_cms_v542.py /srv/atlas/tests/test_cms_v542.py
COPY tests/test_seo_prerender.py /srv/atlas/tests/test_seo_prerender.py
COPY tests/test_unified_seo.py /srv/atlas/tests/test_unified_seo.py
COPY tests/test_seo_audit.py /srv/atlas/tests/test_seo_audit.py
COPY tests/test_page_seo_v57.py /srv/atlas/tests/test_page_seo_v57.py
COPY tests/test_industry_topics_v58.py /srv/atlas/tests/test_industry_topics_v58.py
COPY tests/test_reading_v59.py /srv/atlas/tests/test_reading_v59.py
COPY tests/test_mobile_v60.py /srv/atlas/tests/test_mobile_v60.py
COPY tests/test_geo_sources_v62.py /srv/atlas/tests/test_geo_sources_v62.py
COPY tests/test_discovery_geo_v63.py /srv/atlas/tests/test_discovery_geo_v63.py
COPY tests/test_directory_v64.py /srv/atlas/tests/test_directory_v64.py
COPY tests/test_seo_quality_v65.py /srv/atlas/tests/test_seo_quality_v65.py
COPY tests/test_methodology_v66.py /srv/atlas/tests/test_methodology_v66.py
COPY tests/test_seo_consistency_v68.py /srv/atlas/tests/test_seo_consistency_v68.py
COPY tests/test_topics_v69.py /srv/atlas/tests/test_topics_v69.py
COPY tests/test_global_seo_audit_v70.py /srv/atlas/tests/test_global_seo_audit_v70.py
COPY tests/test_seo_remediation_v71.py /srv/atlas/tests/test_seo_remediation_v71.py
COPY tests/test_seo_history_v72.py /srv/atlas/tests/test_seo_history_v72.py
COPY tests/test_seo_readiness_v73.py /srv/atlas/tests/test_seo_readiness_v73.py
COPY tests/test_seo_final_audit_v74.py /srv/atlas/tests/test_seo_final_audit_v74.py
COPY tests/test_editorial_remediation_v75.py /srv/atlas/tests/test_editorial_remediation_v75.py
COPY tests/test_source_remediation_v76.py /srv/atlas/tests/test_source_remediation_v76.py
COPY tests/test_release_identity.py /srv/atlas/tests/test_release_identity.py
COPY tests/test_auth_workflow_v544.py /srv/atlas/tests/test_auth_workflow_v544.py
COPY tests/browser/cms-v525.spec.mjs /srv/atlas/tests/browser/cms-v525.spec.mjs
RUN bash -n /srv/atlas/scripts/backup-postgres.sh /srv/atlas/scripts/verify-postgres-backup.sh \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_visibility.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_restore_guard.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_admin_guards.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v51.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_taxonomy.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_analytics.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_analytics_growth.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_studio_v513.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v514.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v515.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v520.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v521.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v522.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v524.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v525.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v526.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v527.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v528.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v530.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v531.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v532.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_cms_v542.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_seo_prerender.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_unified_seo.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_seo_audit.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_page_seo_v57.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_industry_topics_v58.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_reading_v59.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_mobile_v60.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_geo_sources_v62.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_discovery_geo_v63.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_directory_v64.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_seo_quality_v65.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_methodology_v66.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_seo_consistency_v68.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_topics_v69.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_global_seo_audit_v70.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_seo_remediation_v71.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_seo_history_v72.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_seo_readiness_v73.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_seo_final_audit_v74.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_editorial_remediation_v75.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_source_remediation_v76.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_release_identity.py" -v \
 && python -m unittest discover -s /srv/atlas/tests -p "test_auth_workflow_v544.py" -v
EXPOSE 8000
CMD ["python","run.py"]
