FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY warp2api-main /app/warp2api-main
COPY account-pool-service /app/account-pool-service
COPY unified_server.py /app/unified_server.py
COPY account.html /app/account.html

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r /app/account-pool-service/requirements.txt
RUN pip install -e /app/warp2api-main

EXPOSE 8080

CMD ["python", "-m", "unified_server"]

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . /app

# Install Python dependencies for both subprojects
RUN pip install --no-cache-dir -U pip setuptools wheel \
  && pip install --no-cache-dir -r /app/account-pool-service/requirements.txt \
  && pip install --no-cache-dir -e /app/warp2api-main

EXPOSE 8080

CMD ["python", "-m", "unified_server"]

