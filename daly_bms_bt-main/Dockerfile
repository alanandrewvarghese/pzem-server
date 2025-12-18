FROM python:3.9-slim

# Install system dependencies
# Added bluez and build-essential (for psycopg2/C-extensions)
RUN apt-get update && apt-get install -y \
    dbus \
    bluez \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

CMD ["python3", "daly_bms_bt.py", "--bt", "C6:6C:09:03:0A:13", "--loop", "5", "--keep"]
