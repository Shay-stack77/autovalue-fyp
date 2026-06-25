# Production-grade container for the FYP valuation API.
# Build:    docker build -t fyp-valuation:latest -f deploy/Dockerfile .
# Run:      docker run --rm -p 8000:8000 fyp-valuation:latest

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# System deps for xgboost + lxml
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# Install production deps first (cached layer)
COPY deploy/requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt

# Copy source
COPY src/ ./src/
COPY frontend/ ./frontend/
COPY wsgi.py ./

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status == 200 else 1)"

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "wsgi:app"]
