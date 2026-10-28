# syntax=docker/dockerfile:1
# Image de production EduIA (API). Contexte de build : le dossier backend/.
# Multi-stage : les dépendances sont installées dans un venv (étape « builder »)
# puis copiées dans une image finale minimale, exécutée par un utilisateur non-root.
# Toutes les dépendances ont des wheels binaires : aucun compilateur n'est requis.

FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-compile -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    PORT=8000
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app knowledge_base ./knowledge_base
COPY --chown=app:app scripts ./scripts
USER app
EXPOSE 8000

# /health ne touche pas la base : le contrôle reste léger (et ne réveille pas Neon).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health',timeout=4)"

# 1) migrations Alembic (idempotent)  2) un seul worker : 512 Mo de RAM sur l'offre gratuite.
# --proxy-headers : récupère la vraie IP cliente derrière le proxy Render (limitation de débit).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips='*' --no-server-header"]
