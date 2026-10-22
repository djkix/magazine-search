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

# Utilisateur non privilégié : l'application et le worker traitent des PDF
# venus du NAS avec Ghostscript, Tesseract et qpdf. Une faille dans l'un de
# ces outils ne doit pas donner root dans le conteneur. UID/GID fixes, pour
# qu'un chown sur l'hôte ou dans un volume reste prévisible d'une version à
# l'autre.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /home/app --create-home \
       --shell /usr/sbin/nologin app

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
# Le code reste la propriété de root : l'utilisateur app peut le lire et
# l'exécuter, pas le modifier.
COPY . .
RUN chmod +x entrypoint.sh

# Seul /data (volume app_data : vignettes, PDF traités, journaux) doit être
# inscriptible. Un volume neuf hérite de ces droits ; un volume créé par une
# version antérieure (propriété de root) doit être repris une fois, voir
# entrypoint.sh. Le montage NAS reste en lecture seule : il suffit qu'il soit
# lisible par l'UID 10001 (ou par un groupe ajouté via group_add).
RUN mkdir -p /data/covers /data/processed /data/logs && chown -R app:app /data

USER app

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
