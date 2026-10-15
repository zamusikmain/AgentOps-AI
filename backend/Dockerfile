FROM python:3.13-slim
WORKDIR /app/backend
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
RUN mkdir -p data
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
