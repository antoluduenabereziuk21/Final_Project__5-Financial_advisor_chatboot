# Financial Advisor Chatbot

Chatbot de asesoramiento financiero basado en RAG (Retrieval-Augmented Generation) que analiza reportes anuales 10-K/20-F de empresas cotizadas en NASDAQ/NYSE/AMEX. Permite consultar métricas financieras, comparar empresas y obtener insights basados en datos reales de los SEC filings.

## Arquitectura

```
┌──────────────┐     POST /api/chat     ┌──────────────────┐
│   Frontend   │ ──────────────────────▶ │     Backend      │
│  React + TS  │ ◀────────────────────── │    FastAPI       │
│  Vite :5173  │     JSON response       │    uvicorn :8000 │
└──────────────┘                         └────────┬─────────┘
                                                  │
                                         ┌────────▼─────────┐
                                         │   RAG Adapter    │
                                         │  (rag/llm +      │
                                         │   rag/retrieval)  │
                                         └───┬──────────┬───┘
                                             │          │
                                    ┌────────▼───┐  ┌──▼──────────┐
                                    │  pgvector  │  │    Groq     │
                                    │  :5432     │  │  LLM API    │
                                    │  185K+     │  │  gpt-oss    │
                                    │  chunks    │  └─────────────┘
                                    └────────────┘
```

### Pipeline RAG

```
PDFs 10-K/20-F → Limpieza → Chunking → Metadata → Embeddings → pgvector
                                                                              │
Usuario pregunta → Embedding pregunta → Búsqueda semántica → Top-K chunks    │
                                                                              │
                                        LLM (Groq) ← Prompt + Contexto ←────┘
                                              │
                                        Respuesta + confidence_flag
```

## Prerrequisitos

| Componente | Versión mínima | Verificar |
|---|---|---|
| Python | 3.11+ | `python --version` |
| Node.js | 20.19+ | `node --version` |
| Docker | 24+ | `docker --version` |
| Docker Compose | v2+ | `docker compose version` |

> **Importante:** Node.js <20.19 causa errores con Vite 8. Actualiza con `nvm install 20 && nvm use 20`.

## Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd Final_Project__5-Financial_advisor_chatboot
```

## Variables de entorno

Copia el example y completa con tus credenciales:

```bash
cp .env.example .env
```

Editar `.env` con tus valores:

```env
# AWS (solo para descargar dataset de S3)
AWS_ACCESS_KEY_ID=tu_access_key
AWS_SECRET_ACCESS_KEY=tu_secret_key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=anyoneai-datasets
S3_PREFIX=nasdaq_annual_reports/
LOCAL_DATA_DIR=data/nasdaq_annual_reports

# Vector Database (pgvector) - LOCAL DOCKER
VECTOR_DB_HOST=localhost
VECTOR_DB_PORT=5432
VECTOR_DB_USER=ml_engineer
VECTOR_DB_PASSWORD=ml_password_2026
VECTOR_DB_NAME=financial_rag_vectors

# pgAdmin (interfaz web para la DB)
PGADMIN_EMAIL=ai_team@empresa.com
PGADMIN_PASSWORD=admin_password_2026
PGADMIN_PORT=8080

# Groq (LLM)
GROQ_API_KEY=tu_groq_api_key_aqui
GROQ_MODEL=openai/gpt-oss-120b

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Obtener API Key de Groq

1. Crear cuenta gratuita en [console.groq.com](https://console.groq.com)
2. Ir a **API Keys** → **Create API Key**
3. Copiar la key (empieza con `gsk_`)
4. Ir a **Project Settings → Limits** y habilitar el modelo `openai/gpt-oss-120b`
5. Pegar la key en `.env` como `GROQ_API_KEY`

> El tier free incluye 30 requests/minuto y 14,400 requests/día. Sin tarjeta de crédito.

## Levantar el proyecto

### Paso 1: Base de datos vectorial (Docker)

```bash
docker compose -f docker/docker-compose.yml up -d
```

Esto levanta:

| Servicio | Puerto | Descripción |
|---|---|---|
| PostgreSQL + pgvector | 5432 | Base de datos vectorial |
| pgAdmin | 8080 | Interfaz web para gestionar la DB |

Verificar que esté corriendo:

```bash
docker compose -f docker/docker-compose.yml ps
```

pgAdmin disponible en `http://localhost:8080` con las credenciales del `.env`.

> **Opción Supabase:** En vez de Docker, puedes usar Supabase. En `.env`, comenta las variables locales y descomenta las de Supabase.

### Paso 2: Backend (Python)

```bash
# Crear virtualenv (si no existe)
python -m venv .venv

# Activar virtualenv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Instalar dependencias
pip install -r backend/requirements.txt
```

Arrancar el backend:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verificar:

```bash
curl http://localhost:8000/health
# {"status":"ok","chunks_indexed":0,"db_connected":true}
```

> Si `chunks_indexed` es 0, necesitas cargar datos en la DB (ver Paso 4).

### Paso 3: Frontend (React)

```bash
cd frontend

# Instalar dependencias
npm install

# Arrancar en modo desarrollo
npm run dev
```

El frontend estará disponible en `http://localhost:5173`.

### Paso 4: Cargar datos en la DB vectorial (Opcional)

Si la DB está vacía (`chunks_indexed: 0`), necesitas ingestar los reportes:

```bash
# Descargar dataset desde S3 (requiere credenciales AWS)
pip install -r rag/dataset/requirements.txt
python rag/dataset/download_dataset_parallel.py

# Procesar un reporte individual
python -m rag.ingestion.orchestrate ruta/al/reporte.pdf

# Bulk load a la DB (desde archivos ya procesados)
python rag/bulk_load.py
```

Ver `rag/README.md` para documentación completa del pipeline de ingestion.

## Resumen de servicios

| Servicio | URL | Descripción |
|---|---|---|
| Frontend | http://localhost:5173 | Interfaz de chat (React) |
| Backend API | http://localhost:8000 | API REST (FastAPI) |
| Backend Docs | http://localhost:8000/docs | Swagger/OpenAPI |
| pgAdmin | http://localhost:8080 | Admin de PostgreSQL |
| PostgreSQL | localhost:5432 | Base de datos vectorial |

## API Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio + chunks indexados |
| GET | `/api/welcome` | Mensaje de bienvenida |
| POST | `/api/chat` | Enviar mensaje al chatbot |

### POST /api/chat

```json
// Request
{
  "message": "¿Cuál fue el revenue de Apple en 2023?",
  "session_id": "abc123"
}

// Response
{
  "reply": "Apple reportó un revenue de $383.3 mil millones en el fiscal 2023...",
  "confidence_flag": "ok",
  "sources": [...]
}
```

#### confidence_flag

| Flag | Significado |
|---|---|
| `ok` | Respuesta generada con certeza suficiente |
| `low_confidence` | Scores de similitud bajos |
| `entity_not_found` | No se encontró la empresa/año en la DB |
| `subjective_no_verdict` | Pregunta subjetiva, solo datos sin veredicto |

## Comandos Docker útiles

```bash
# Levantar todo
docker compose -f docker/docker-compose.yml up -d

# Detener (datos persisten)
docker compose -f docker/docker-compose.yml down

# Destruir todo (borra la DB)
docker compose -f docker/docker-compose.yml down -v

# Ver logs
docker compose -f docker/docker-compose.yml logs -f

# Ver logs de un servicio específico
docker compose -f docker/docker-compose.yml logs -f postgres_vector
```

## Tech Stack

| Capa | Tecnología |
|---|---|
| Frontend | React 19, TypeScript, Vite 8, TailwindCSS 4, shadcn/ui |
| Backend | FastAPI, Python 3.12, uvicorn |
| LLM | Groq API (`openai/gpt-oss-120b`) |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`, 384 dims) |
| Vector DB | PostgreSQL 16 + pgvector (HNSW index) |
| DB Admin | pgAdmin 4 |
| DI (Frontend) | Inversify |
| HTTP Client | Axios |
| Infra | Docker, Docker Compose |

## Estructura del proyecto

```
├── .env                    Variables de entorno (no commitear)
├── backend/                API FastAPI
│   ├── app/
│   │   ├── main.py         Entry point + lifespan
│   │   ├── api/            Rutas HTTP (chat, welcome)
│   │   ├── core/           Configuración y settings
│   │   ├── models/         Modelos Pydantic
│   │   ├── rag/            Adapter al pipeline RAG
│   │   └── services/       Lógica de negocio
│   └── requirements.txt
├── frontend/               React SPA
│   ├── src/
│   │   ├── data/           Repositorios, HTTP client
│   │   ├── domain/         Entidades y contratos
│   │   └── presentation/   Componentes, hooks, páginas
│   └── package.json
├── rag/                    Pipeline RAG completo
│   ├── dataset/            Descarga desde S3
│   ├── ingestion/          Limpieza, chunking, metadata
│   ├── embeddings/         Generación de vectores
│   ├── vector_store/       Conexión pgvector + CRUD
│   ├── retrieval/          Búsqueda semántica
│   └── llm/                Generación con Groq
├── docker/                 Docker Compose + configs
│   └── docker-compose.yml  PostgreSQL + pgAdmin
└── docs/                   Documentación adicional
```

## Troubleshooting

### Backend no conecta a la DB

```
Could not connect to vector DB – running without RAG retrieval
```

- Verificar que Docker esté corriendo: `docker compose -f docker/docker-compose.yml ps`
- Verificar que el puerto 5432 esté libre
- El backend funciona en modo degradado sin DB (respuestas simuladas)

### Frontend no compila / Vite error

```
Error: Node.js version too old
```

- Actualizar Node.js a v20.19+: `nvm install 20 && nvm use 20`
- O usar `npx vite build --force`

### Groq responde "model blocked"

- Ir a [console.groq.com/settings/project/limits](https://console.groq.com/settings/project/limits)
- Habilitar el modelo `openai/gpt-oss-120b`

### Errores de encoding en Windows

Si ves `UnicodeEncodeError` en la consola, es un problema de encoding de PowerShell. Los datos se procesan correctamente internamente.

### Puertos en uso

```bash
# Ver qué usa el puerto 5432
netstat -ano | findstr :5432

# Matar proceso por PID
taskkill /PID <pid> /F
```
