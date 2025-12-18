FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps:
# - bluez/dbus: BLE access via BlueZ
# - libpq-dev + build tools: psycopg2 builds if wheel unavailable
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bluez \
        dbus \
        libpq-dev \
        gcc \
        libc6-dev \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
COPY web/requirements.txt ./web/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt -r web/requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "web/app.py"]
