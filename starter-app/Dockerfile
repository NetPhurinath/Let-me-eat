# NoteVault image — hardened: pinned slim base, deps installed before code for caching,
# only the app copied in, no secrets baked in (APP_SECRET is supplied at runtime), non-root user.
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

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
