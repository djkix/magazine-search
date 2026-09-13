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
