FROM python:3.9-slim

# Install system dependencies required for bleak (Bluetooth) and psycopg2
FROM python:3.9-slim

# 1. Install system dependencies
# Added bluez and build-essential (for psycopg2/C-extensions)
RUN apt-get update && apt-get install -y \
    dbus \
    bluez \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Python dependencies
# Keeping this separate ensures that editing your code 
# doesn't trigger a re-download of all pip packages.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy application
COPY . .

CMD ["python3", "daly_bms_bt.py", "--loop", "60", "--log-level", "info"]

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Set the entrypoint
CMD ["python3", "daly_bms_bt.py", "--loop", "60", "--log-level", "info"]
