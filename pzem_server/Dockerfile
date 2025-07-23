FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# CMD ["uvicorn", "app:api", "--host", "0.0.0.0", "--port", "8000"]
CMD ["python", "main.py"]