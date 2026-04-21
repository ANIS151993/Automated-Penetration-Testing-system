FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./pyproject.toml
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY scripts/start-backend.sh /usr/local/bin/start-backend

RUN pip install . \
    && chmod +x /usr/local/bin/start-backend

EXPOSE 8000

CMD ["start-backend"]
