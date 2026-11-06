# NoteVault image — hardened: pinned slim base, deps installed before code for caching,
# only the app copied in, no secrets baked in (APP_SECRET is supplied at runtime), non-root user.
FROM python:3.12-slim@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0

WORKDIR /app
COPY requirements.lock .
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin notevault

COPY app.py .

USER notevault
EXPOSE 8080
CMD ["python", "app.py"]
