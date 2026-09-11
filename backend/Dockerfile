# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS runtime

# Runtime dependencies for ocrmypdf/Tesseract (fra+eng) and PDF rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-eng \
    ghostscript \
    qpdf \
    && rm -rf /var/lib/apt/lists/*

# pg_dump, pour la sauvegarde prise juste avant une migration (entrypoint.sh).
#
# La version majeure doit valoir AU MOINS celle du serveur : pg_dump refuse de
# sauvegarder une base plus recente que lui. Debian ne fournit qu'une version
# figee au nom de la distribution, en retard sur postgres:16 en production —
# d'ou le depot officiel PostgreSQL, seul moyen d'obtenir exactement la 16.
#
# Le nom de code (bookworm, trixie...) est lu dans /etc/os-release plutot que
# figé en dur : `python:3.12-slim` a changé de base entre bookworm et trixie
# sans changement de tag, et un nom de code codé en dur pour l'un installe un
# libpq5 incompatible avec l'autre (conflit avec libldap notamment).
#
# A METTRE A JOUR en meme temps que l'image postgres du docker-compose.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] http://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-16 \
    && apt-get purge -y curl gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
# PYTHONPATH : Python place le repertoire DU SCRIPT dans sys.path, pas le
# repertoire courant. « python tools/xxx.py » ne trouvait donc pas le paquet
# app, et tout script de tools/ echouait sur ModuleNotFoundError — y compris
# diagnostiquer_sommaire.py, dont l'usage documente n'a jamais pu fonctionner.
# Pose ici plutot qu'en tete de chaque script, pour valoir aussi pour les
# outils a venir.
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY . .
RUN chmod +x entrypoint.sh

RUN mkdir -p /data/covers /data/processed

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
