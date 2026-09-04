# Base de datos — Schema y puesta en marcha

Documento para el equipo. Describe las tablas de la base `financial_rag_vectors`
(PostgreSQL 16 + pgvector) y los comandos para levantar una instancia local.

Referencia funcional: `docs/rag_pipeline_contrato.docx` (sección 2.1).

---

## Cómo levantar la base de datos

Requiere Docker. Las 6 tablas se crean **automáticamente en el primer arranque**
del contenedor: `rag/vector_store/init_db.sql` se monta en
`/docker-entrypoint-initdb.d/` (ver `docker/docker-compose.yml`).

### Opción 1 — Script (`./rag/init_db.sh`)

Requiere bash (Git Bash / WSL / Linux):

```bash
./rag/init_db.sh
```

Levanta Postgres + pgvector + pgAdmin, espera a que el motor responda y aplica
el schema (idempotente, seguro de re-ejecutar).

### Opción 2 — Docker Compose directo

```bash
docker compose -f docker/docker-compose.yml up -d postgres_vector pgadmin
```

### Verificar

```bash
docker exec rag_vector_db psql -U ml_engineer -d financial_rag_vectors -c "\dt"
```

Debe listar las 6 tablas: `users`, `conversations`, `chat_messages`,
`companies`, `documents`, `rag_chunks`.

> Nota: si ya existía un volumen con datos previos, el init automático no se
> vuelve a ejecutar (solo corre sobre volumen vacío). En ese caso re-aplicar el
> schema manualmente:
> `docker exec -i rag_vector_db psql -U ml_engineer -d financial_rag_vectors < rag/vector_store/init_db.sql`

### Credenciales por defecto (sobreescribibles en `.env`)

| Variable | Default | Uso |
|---|---|---|
| `VECTOR_DB_HOST` | `localhost` | Host de Postgres/pgvector |
| `VECTOR_DB_PORT` | `5432` | Puerto |
| `VECTOR_DB_USER` | `ml_engineer` | Usuario |
| `VECTOR_DB_PASSWORD` | `ml_password_2026` | Contraseña |
| `VECTOR_DB_NAME` | `financial_rag_vectors` | Base de datos |
| `PGADMIN_PORT` | `8080` | UI de pgAdmin |
| `PGADMIN_EMAIL` | `ai_team@empresa.com` | Login pgAdmin |
| `PGADMIN_PASSWORD` | `admin_password_2026` | Login pgAdmin |

### pgAdmin

1. Abrir http://localhost:8080 y loguearse con `PGADMIN_EMAIL` / `PGADMIN_PASSWORD`.
2. *Object → Register → Server*:
   - **Host**: `rag_vector_db` (nombre del contenedor en la red docker, **no** `localhost`)
   - Port: `5432` · Username: `ml_engineer` · Password: `ml_password_2026`
   - Database (maintenance): `financial_rag_vectors`
3. Ver las tablas en `financial_rag_vectors → Schemas → public → Tables`.

---

## Tablas

### Aplicación (Postgres relacional)

#### `users`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `BIGSERIAL` PK | |
| `email` | `TEXT` UNIQUE NOT NULL | |
| `username` | `TEXT` UNIQUE NOT NULL | |
| `password_hash` | `TEXT` NOT NULL | |
| `is_active` | `BOOLEAN` DEFAULT TRUE | |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

#### `conversations`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `UUID` PK DEFAULT `gen_random_uuid()` | |
| `user_id` | `BIGINT` FK → `users(id)` ON DELETE CASCADE | nullable (sesiones anónimas) |
| `title` | `TEXT` DEFAULT 'Nueva conversacion' | |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

#### `chat_messages`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `BIGSERIAL` PK | |
| `conversation_id` | `UUID` FK → `conversations(id)` ON DELETE CASCADE | |
| `role` | `TEXT` CHECK (`'user'` \| `'assistant'`) | |
| `content` | `TEXT` NOT NULL | |
| `sources` | `JSONB` | array de fuentes (contrato 2.1) |
| `confidence_flag` | `TEXT` | `ok` / `low_confidence` / `entity_not_found` / `subjective_no_verdict` |
| `retrieval_meta` | `JSONB` | metadata del retrieval |
| `created_at` | `TIMESTAMPTZ` | |

#### `message_feedback`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `BIGSERIAL` PK | |
| `message_id` | `BIGINT` FK → `chat_messages(id)` ON DELETE CASCADE | |
| `conversation_id` | `UUID` FK → `conversations(id)` ON DELETE CASCADE | |
| `rating` | `TEXT` CHECK (`'up'` \| `'down'`) | |
| `reason` | `TEXT` | opcional |
| `user_id` | `BIGINT` FK → `users(id)` ON DELETE SET NULL | nullable (sesiones anónimas) |
| `created_at` | `TIMESTAMPTZ` | |

### RAG vectorial (pgvector)

#### `companies`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `BIGSERIAL` PK | |
| `ticker` | `TEXT` UNIQUE NOT NULL | |
| `company` | `TEXT` NOT NULL | |

#### `documents`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `BIGSERIAL` PK | |
| `company_id` | `BIGINT` FK → `companies(id)` ON DELETE SET NULL | |
| `source_file` | `TEXT` UNIQUE NOT NULL | ruta del PDF indexado |
| `company` | `TEXT` NOT NULL | |
| `ticker` | `TEXT` NOT NULL | |
| `fiscal_year` | `INT` NOT NULL | |
| `form_type` | `TEXT` | 10-K / 20-F — metadata, **no** filtro (contrato 1.2) |
| `accounting_standard` | `TEXT` | US GAAP / IFRS — metadata, **no** filtro (contrato 1.2) |
| `indexed_at` | `TIMESTAMPTZ` | |

#### `rag_chunks`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | `BIGSERIAL` PK | `chunk_id` |
| `document_id` | `BIGINT` FK → `documents(id)` ON DELETE CASCADE | |
| `chunk_index` | `INT` NOT NULL | expandir vecinos (contrato 3.4) |
| `content` | `TEXT` NOT NULL | texto del chunk |
| `embedding` | `VECTOR(384)` NOT NULL | all-MiniLM-L6-v2 |
| `ticker` | `TEXT` NOT NULL | filtro confirmado |
| `company` | `TEXT` NOT NULL | filtro confirmado |
| `fiscal_year` | `INT` NOT NULL | filtro confirmado |
| `form_type` | `TEXT` | metadata, no filtro |
| `accounting_standard` | `TEXT` | metadata, no filtro |
| `canonical_section` | `TEXT` | ej. "Balance Sheet" (nullable) |
| `source_file` | `TEXT` NOT NULL | cita al PDF original |
| `page_start` / `page_end` | `INT` | cita de páginas |
| `numeric_density` | `REAL` | densidad numérica del chunk |
| `created_at` | `TIMESTAMPTZ` | |

---

## Índices

| Índice | Tabla | Tipo / Columnas | Uso |
|---|---|---|---|
| `idx_rag_chunks_hnsw` | `rag_chunks` | HNSW `embedding vector_cosine_ops` | búsqueda por similitud |
| `idx_rag_chunks_ticker_year` | `rag_chunks` | `(ticker, fiscal_year)` | pre-filtrado por metadata |
| `idx_rag_chunks_document` | `rag_chunks` | `(document_id, chunk_index)` | expansión de vecinos |
| `idx_documents_ticker_year` | `documents` | `(ticker, fiscal_year)` | consultas por documento |
| `idx_conversations_user_id` | `conversations` | `(user_id)` | chat por usuario |
| `idx_chat_messages_conversation` | `chat_messages` | `(conversation_id, id)` | historial por conversación |
| `idx_message_feedback_message` | `message_feedback` | `(message_id)` | feedback por mensaje |

Uniques: `users.email`, `users.username`, `companies.ticker`, `documents.source_file`.

---

## Modelos Python

- `rag/vector_store/models.py` — `ChunkRecord`, `SearchResult`, `SearchParams`
  (RAG/pgvector) y `UserRecord`, `ConversationRecord`, `ChatMessageRecord` (aplicación).
- `rag/vector_store/repository.py` — acceso asyncpg (insert, `search_similar` con
  filtros tipados, `get_neighbors`, `count`, `get_by_id`, `delete_all`).
- `backend/app/repositories/conversation_repository.py` — persiste
  `conversations`/`chat_messages`/`message_feedback` reutilizando el pool de
  `VectorDbClient` ya conectado en `backend/app/main.py` (no abre una conexión
  propia). Solo se activa en el camino de Postgres directo; en modo Supabase
  (HTTPS/RPC de solo lectura) o sin backend conectado, `ConversationService` y
  `ChatService` caen a estado en memoria (se pierde al reiniciar el proceso).
  Ver `docs/adr/0001-conversation-persistence.md`.
