#!/bin/bash
set -e

echo "==> Levantando Postgres + pgvector + pgAdmin..."
docker compose -f docker/docker-compose.yml up -d

echo "==> Esperando respuesta del motor PostgreSQL..."
until docker exec rag_vector_db pg_isready -U "${VECTOR_DB_USER:-ml_engineer}" -d "${VECTOR_DB_NAME:-financial_rag_vectors}" > /dev/null 2>&1; do
  sleep 1
done

echo "==> Instalando extensión pgvector e inicializando schema..."
docker exec -i rag_vector_db psql -U "${VECTOR_DB_USER:-ml_engineer}" -d "${VECTOR_DB_NAME:-financial_rag_vectors}" < rag/vector_store/init_db.sql

echo ""
echo "=========================================================="
echo "  ENTORNO AI/ML CONFIGURADO"
echo "=========================================================="
echo "  DB Connection: postgresql://${VECTOR_DB_USER:-ml_engineer}:${VECTOR_DB_PASSWORD:-ml_password_2026}@localhost:${VECTOR_DB_PORT:-5432}/${VECTOR_DB_NAME:-financial_rag_vectors}"
echo "  pgAdmin 4 UI: http://localhost:${PGADMIN_PORT:-8080}"
echo "  Usuario pgAdmin: ${PGADMIN_EMAIL:-ai_team@empresa.com}"
echo "=========================================================="
