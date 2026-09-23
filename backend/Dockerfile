# Multi-stage: one image, dev + production targets (spec Part 7.5 parity).
FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# --- dev target: hot reload via flask run, plus the test tooling ---
FROM base AS dev
ENV FLASK_APP=wsgi.py FLASK_DEBUG=1
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]

# --- production target: gunicorn ---
FROM base AS production
ENV FLASK_ENV=production
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "wsgi:app"]
