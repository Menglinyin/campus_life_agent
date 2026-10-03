FROM python:3.12-slim
ARG INSTALL_RAG=false
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HOME=/srv/model-cache
WORKDIR /srv/project
COPY backend/requirements.txt backend/requirements-rag.txt ./backend/
COPY config/requirements.txt ./config/
RUN pip install --no-cache-dir -r backend/requirements.txt -r config/requirements.txt     && if [ "$INSTALL_RAG" = "true" ]; then pip install --no-cache-dir -r backend/requirements-rag.txt; fi
COPY backend/app ./backend/app
COPY backend/skill_packages ./backend/skill_packages
COPY config ./config
COPY data ./data
COPY deployment/entrypoint.sh /usr/local/bin/campus-entrypoint
RUN groupadd --gid 10001 campus && useradd --uid 10001 --gid campus --no-create-home campus     && mkdir -p /srv/runtime /srv/chroma /srv/model-cache /srv/project/data/local     && chown -R campus:campus /srv/runtime /srv/chroma /srv/model-cache /srv/project/data/local     && chmod 755 /usr/local/bin/campus-entrypoint
USER 10001:10001
ENTRYPOINT ["/usr/local/bin/campus-entrypoint"]
CMD ["python", "config/launch.py", "--host", "0.0.0.0", "--port", "8000"]
