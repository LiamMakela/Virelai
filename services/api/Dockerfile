FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app

CMD ["opentelemetry-instrument","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]