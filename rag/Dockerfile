FROM python:3.12-slim

WORKDIR /app

COPY rag/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "rag.app:app", "--host", "0.0.0.0", "--port", "8000"]
