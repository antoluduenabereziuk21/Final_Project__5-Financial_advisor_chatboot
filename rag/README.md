# RAG — Retrieval-Augmented Generation Pipeline

Pipeline completo para el asistente financiero: descarga de PDFs 10-K/20-F →
limpieza → chunking → embeddings → almacenamiento vectorial → retrieval →
generación con LLM.

---

## Estructura del módulo

```
rag/
├── dataset/               Descarga del corpus NASDAQ desde S3
│   ├── download_dataset.py           Secuencial
│   ├── download_dataset_parallel.py  Paralelo (recomendado)
│   └── README.md
├── ingestion/             Pipeline de preprocessing
│   ├── cleaning.py        Extracción de texto, front-matter, boilerplate
│   ├── chunking.py        Haystack word-count + structure-aware chunking
│   ├── metadata.py        Detección de form_type, fiscal_year, accounting_standard
│   ├── canonical_sections.py  Mapeo 10-K / 20-F a secciones canónicas
│   ├── orchestrate.py     Orquestador cleaning → chunking → metadata
│   ├── SPEC.md            Documentación técnica del pipeline v2
│   └── RESULTS.md         Resultados sobre 10 reportes de prueba
├── vector_store/          Conexión a pgvector + CRUD
│   ├── client.py          Connection pool asyncpg
│   ├── repository.py      Insert, search_similar, init_schema
│   ├── models.py          ChunkRecord, SearchResult, SearchParams
│   └── init_db.sql        Schema SQL rag_documents + índices HNSW/GIN
├── embeddings/            Generación de embeddings con all-MiniLM-L6-v2
│   └── generate.py        embed_text(), embed_batch() — 384 dimensiones
├── retrieval/             Búsqueda semántica + filtros por metadata
│   └── retriever.py       retrieve() con post-filter y formateo de sources[]
├── llm/                   Generación con LLM + confidence_flag
│   └── generator.py       Prompt, respuesta, flags: ok / low_confidence / entity_not_found / subjective_no_verdict
├── app.py                 FastAPI entrypoint para el servicio RAG
├── Dockerfile             Imagen Docker del servicio RAG
├── init_db.sh             Script: levanta pgvector + pgAdmin con Docker
└── requirements.txt       Dependencias consolidadas
```

---

## Setup completo

### 1. Prerrequisitos

- Python 3.11+
- Docker (para la base de datos vectorial)
- Credenciales AWS en `.env` (solo para descargar el dataset)

### 2. Base de datos vectorial

Levanta PostgreSQL 16 con pgvector + pgAdmin 4:

```bash
./rag/init_db.sh
```

Esto inicia los contenedores, instala la extensión `vector` y deja la base
lista para recibir chunks con embeddings.

Credenciales por defecto — ver `docker/docker-compose.yml` o el output del script.

### 3. Instalar dependencias

```bash
pip install -r rag/requirements.txt
```

### 4. (Opcional) Descargar dataset

```bash
pip install -r rag/dataset/requirements.txt
python rag/dataset/download_dataset_parallel.py
```

Ver `rag/dataset/README.md` para más opciones.

### 5. Ejecutar ingestion (procesar un PDF)

```bash
python -m rag.ingestion.orchestrate ruta/al/reporte.pdf
```

El output se guarda en `rag/ingestion/output/<nombre>.json` con los chunks,
metadatos y reporte de limpieza.

### 6. Iniciar el servicio RAG (Docker)

```bash
docker build -t rag-service -f rag/Dockerfile .
docker run -p 8000:8000 --env-file .env rag-service
```

---

## Flujo del pipeline

```
PDF 10-K/20-F
     │
     ▼
┌─────────────┐
│  cleaning   │  Extrae texto, salta front-matter, remueve boilerplate,
│             │  dehyphenation, deglue_words, normaliza whitespace
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  chunking   │  Dos estrategias: word_count (Haystack, 350 palabras)
│             │  y structure_then_word_count (por ítems SEC)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  metadata   │  Detecta form_type, fiscal_year, accounting_standard,
│             │  canonical_section, numeric_density
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ embeddings  │  Genera vectores 384-d con all-MiniLM-L6-v2
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ vector_store│  Almacena en pgvector con índices HNSW para búsqueda
│  (pgvector) │  rápida por similitud de coseno
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  retrieval  │  Embed pregunta + filtros metadata → top-k chunks
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    LLM      │  Prompt con contexto → respuesta + confidence_flag
└─────────────┘
```

---

## Comandos útiles

### Iniciar infraestructura
```bash
./rag/init_db.sh
```

### Detener contenedores (datos persisten)
```bash
docker compose -f docker/docker-compose.yml down
```

### Destruir todo (borra la DB)
```bash
docker compose -f docker/docker-compose.yml down -v
```

### Ver logs de la DB
```bash
docker compose -f docker/docker-compose.yml logs -f
```

### Construir y ejecutar servicio RAG
```bash
docker build -t rag-service -f rag/Dockerfile .
docker run -p 8000:8000 --env-file .env rag-service
```

---

## Endpoints del servicio RAG

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio + documentos indexados |
| POST | `/query` | Pregunta → retrieval → respuesta del LLM (endpoint principal) |
| POST | `/search` | Búsqueda semántica directa (legacy, devuelve sources sin LLM) |
| POST | `/ingest` | Procesar un PDF e indexarlo en la DB vectorial |

### POST /query

Request:
```json
{
  "question": "¿Cuál fue el revenue de NCLH en 2020?",
  "session_id": "abc123",
  "filters": {
    "ticker": ["NCLH"],
    "company": ["Norwegian Cruise Line"],
    "fiscal_year": 2020
  },
  "top_k": 5
}
```

Response:
```json
{
  "answer": "Norwegian Cruise Line reportó un revenue de $X millones en 2020...",
  "confidence_flag": "ok",
  "sources": [
    {
      "chunk_id": 42,
      "company": "Norwegian Cruise Line",
      "ticker": "NCLH",
      "fiscal_year": 2020,
      "form_type": "10-K",
      "accounting_standard": "US GAAP",
      "canonical_section": "mdna",
      "source_file": ".../NCLH_2020.pdf",
      "page_start": 45,
      "page_end": 46,
      "relevance_score": 0.87,
      "text_snippet": "Revenue decreased by $X million..."
    }
  ],
  "retrieval_meta": {
    "filters_applied": { "ticker": ["NCLH"], "fiscal_year": 2020 },
    "chunks_considered": 5,
    "model": "all-MiniLM-L6-v2"
  }
}
```

#### confidence_flag

| Flag | Significado |
|---|---|
| `ok` | Respuesta generada con suficiente certeza |
| `low_confidence` | Scores de similitud bajos — respuesta puede ser imprecisa |
| `entity_not_found` | No se encontraron chunks para la empresa/año solicitados |
| `subjective_no_verdict` | Pregunta subjetiva — se presentan datos sin veredicto |

---

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `VECTOR_DB_HOST` | `localhost` | Host de pgvector |
| `VECTOR_DB_PORT` | `5432` | Puerto de pgvector |
| `VECTOR_DB_USER` | `ml_engineer` | Usuario de la base de datos |
| `VECTOR_DB_PASSWORD` | `ml_password_2026` | Contraseña |
| `VECTOR_DB_NAME` | `financial_rag_vectors` | Nombre de la base de datos |
| `OPENAI_API_KEY` | — | API key para OpenAI (si se usa GPT como LLM) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Modelo de OpenAI para generación |

---

## Dependencias principales

- **pdfplumber** — Extracción de texto de PDFs
- **haystack-ai** — Chunking y pipelines de NLP
- **wordninja** — Segmentación de tokens sin espacios
- **sentence-transformers** — Embeddings con all-MiniLM-L6-v2 (384 dim)
- **asyncpg** — Conexión a PostgreSQL asíncrona
- **boto3** — Descarga del dataset desde S3
- **openai** — LLM para generación de respuestas
- **FastAPI + uvicorn** — Servicio REST (contenedor Docker)
