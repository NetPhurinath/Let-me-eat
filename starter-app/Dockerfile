# NoteVault image — hardened: pinned slim base, deps installed before code for caching,
# only the app copied in, no secrets baked in (APP_SECRET is supplied at runtime), non-root user.
FROM python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin notevault

COPY app.py .

USER notevault
EXPOSE 8080
CMD ["python", "app.py"]
