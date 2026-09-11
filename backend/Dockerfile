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
# sauvegarder une base plus recente que lui. Bookworm ne fournit que la 15
# alors que la production tourne en postgres:16 — d'ou le depot officiel
# PostgreSQL, seul moyen d'obtenir exactement la 16.
#
# A METTRE A JOUR en meme temps que l'image postgres du docker-compose.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-16 \
    && apt-get purge -y curl gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .
RUN chmod +x entrypoint.sh

RUN mkdir -p /data/covers /data/processed

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
