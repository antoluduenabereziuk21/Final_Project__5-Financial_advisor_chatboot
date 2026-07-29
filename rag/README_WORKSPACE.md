# AI/ML Data Layer: Vector Database Workspace

Este entorno unificado está diseñado exclusivamente para el equipo de **AI/ML Engineers**. Provee una instancia aislada de PostgreSQL con soporte nativo de vectores (`pgvector`) para almacenar fragmentos (chunks) y embeddings generados por el pipeline RAG (Haystack), junto a la interfaz gráfica **pgAdmin 4** para la auditoría y análisis de los datos.

Al estar completamente aislado, el equipo de desarrollo de Backend tradicional puede levantar su propia base transaccional sin interferir con las operaciones pesadas de búsqueda vectorial.

---

## 1. Configuración de Orquestación (`docker-compose.yml`)

Crea un archivo llamado `docker-compose.yml` y pega el siguiente contenido. Este archivo define la base de datos vectorial, la interfaz web y los volúmenes para asegurar la persistencia local de los vectores.

```yaml
version: '3.8'

services:
  postgres_vector:
    image: pgvector/pgvector:pg16
    container_name: rag_vector_db
    restart: always
    environment:
      POSTGRES_USER: ml_engineer
      POSTGRES_PASSWORD: ml_password_2026
      POSTGRES_DB: financial_rag_vectors
    ports:
      - "5432:5432"
    volumes:
      - ml_vector_data:/var/lib/postgresql/data
    networks:
      - rag_network

  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: rag_pgadmin
    restart: always
    environment:
      PGADMIN_DEFAULT_EMAIL: ai_team@empresa.com
      PGADMIN_DEFAULT_PASSWORD: admin_password_2026
    ports:
      - "8080:80"
    volumes:
      - ml_pgadmin_data:/var/lib/pgadmin
    networks:
      - rag_network
    depends_on:
      - postgres_vector

volumes:
  ml_vector_data:
    driver: local
  ml_pgadmin_data:
    driver: local

networks:
  rag_network:
    driver: bridge
```

---

## 2. Script de Automatización de Consola (`init_db.sh`)

Crea un archivo llamado `init_db.sh`. Este script de Bash enciende los servicios, espera a que el motor esté listo para recibir conexiones y ejecuta de manera interna el comando SQL necesario para activar la extensión vector sin intervención humana.

```bash
#!/bin/bash
set -e

echo "🚀 [AI/ML Env] Levantando Postgres + pgvector + pgAdmin..."
docker compose up -d

echo "⏳ Esperando respuesta del motor PostgreSQL..."
until docker exec rag_vector_db pg_isready -U ml_engineer -d financial_rag_vectors > /dev/null 2>&1; do
  sleep 1
done

echo "⚙️  Instalando extensión pgvector en la base de datos de embeddings..."
docker exec -i rag_vector_db psql -U ml_engineer -d financial_rag_vectors -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "=========================================================="
echo "✅ ENTORNO AI/ML CONFIGURADO"
echo "=========================================================="
echo "🔗 DB Connection: postgresql://ml_engineer:ml_password_2026@localhost:5432/financial_rag_vectors"
echo "🖥️  pgAdmin 4 UI: http://localhost:8080"
echo "👤 Usuario pgAdmin: ai_team@empresa.com"
echo "🔑 Clave pgAdmin: admin_password_2026"
echo "=========================================================="
```

> 💡 **Nota de ejecución:** Antes de lanzar el script por primera vez en entornos basados en Unix (Linux/macOS), debes otorgarle permisos de ejecución con el comando: `chmod +x init_db.sh`

---

## 3. Guía de Uso del Workspace

### Cómo Inicializar el Entorno
Ejecuta el script desde tu terminal:
```bash
./init_db.sh
```

### Credenciales de Desarrollo (AI/ML Stack)
* **Base de Datos Vectorial:**
  * **Host:** `localhost` | **Port:** `5432`
  * **User:** `ml_engineer` | **Password:** `ml_password_2026`
  * **Database:** `financial_rag_vectors`
* **Consola Visual pgAdmin 4:**
  * **URL:** [http://localhost:8080](http://localhost:8080)
  * **Login:** `ai_team@empresa.com` | **Password:** `admin_password_2026`

⚠️ **Tip crítico para registrar el servidor en pgAdmin:** Cuando añadas la base de datos dentro de la interfaz web de pgAdmin (pestaña *Connection*), escribe `postgres_vector` en el campo **Host name/address** en lugar de `localhost`. Esto permite que pgAdmin se comunique de forma directa a través de la red interna de Docker (`rag_network`).

---

## 4. Estructura de Tabla e Ingesta de Datos (SQL)

Una vez que accedas a la base de datos mediante pgAdmin o mediante tu script en Python, la tabla recomendada para almacenar tus JSONs procesados junto a sus metadatos estructurados es la siguiente:

```sql
-- Crear la tabla para el almacenamiento del pipeline RAG
CREATE TABLE rag_documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,                          -- Fragmento de texto extraído
    embedding VECTOR(1536) NOT NULL,               -- Cambiar 1536 según la dimensión de tu modelo
    metadata JSONB NOT NULL,                       -- Almacenamiento dinámico de metadatos (archivo, página, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Crear índice HNSW para búsquedas vectoriales rápidas en producción
CREATE INDEX ON rag_documents USING hnsw (embedding vector_cosine_ops);

-- Crear índice GIN en la metadata para permitir filtrados rápidos previos al RAG
CREATE INDEX idx_rag_metadata ON rag_documents USING gin (metadata);
```

### Consulta de Prueba Semántica (Auditoría)
Para simular el comportamiento del componente *Retriever* de Haystack y auditar la calidad de las respuestas directly en SQL:

```sql
-- Buscar los 3 fragmentos más cercanos por similitud de coseno y calcular porcentaje de acierto
SELECT content, metadata, (1 - (embedding <=> '[0.015, -0.023, ...]')) AS similarity
FROM rag_documents
ORDER BY embedding <=> '[0.015, -0.023, ...]'
LIMIT 3;
```

---

## 5. Comandos Útiles de Administración (Docker)

* **Detener los contenedores (guardando los vectores existentes):**
  ```bash
  docker compose down
  ```
* **Visualizar los logs internos en tiempo real para debugging:**
  ```bash
  docker compose logs -f
  ```
* **Destruir por completo el entorno borrando todas las bases de datos:**
  ```bash
  docker compose down -v
  ```
