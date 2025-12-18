FROM python:3.9-slim

# Install system dependencies required for bleak (Bluetooth) and psycopg2
RUN apt-get update && apt-get install -y \
    bluez \
    dbus \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Set the entrypoint
CMD ["python3", "daly_bms_bt.py", "--loop", "60", "--log-level", "info"]
