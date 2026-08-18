-- ============================================================================
-- Esquema de base de datos: financial_rag_vectors (PostgreSQL 16 + pgvector)
-- Contrato de referencia: docs/rag_pipeline_contrato.docx (seccion 2.1)
-- Dos grupos de tablas:
--   1. Aplicacion (Postgres relacional): users, conversations, chat_messages
--   2. RAG vectorial (pgvector): companies, documents, rag_chunks
-- Idempotente: seguro ejecutarlo multiples veces (IF NOT EXISTS).
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ----------------------------------------------------------------------------
-- Aplicacion: usuarios
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Aplicacion: conversaciones (hilos de chat)
-- user_id nullable: permite sesiones anonimas antes de autenticacion.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL DEFAULT 'Nueva conversacion',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);

-- ----------------------------------------------------------------------------
-- Aplicacion: mensajes de chat
-- sources / retrieval_meta siguen la estructura del contrato (array de fuentes
-- + metadata del retrieval) y se guardan como JSONB por su tamano variable.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    sources         JSONB,
    confidence_flag TEXT,
    retrieval_meta  JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation
    ON chat_messages(conversation_id, id);

-- ----------------------------------------------------------------------------
-- RAG: companies (referencia, ticker unico)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS companies (
    id      BIGSERIAL PRIMARY KEY,
    ticker  TEXT NOT NULL UNIQUE,
    company TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- RAG: documents (un PDF 10-K/20-F indexado)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id                  BIGSERIAL PRIMARY KEY,
    company_id          BIGINT REFERENCES companies(id) ON DELETE SET NULL,
    source_file         TEXT NOT NULL UNIQUE,
    company             TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    fiscal_year         INT NOT NULL,
    form_type           TEXT,
    accounting_standard TEXT,
    indexed_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_ticker_year ON documents(ticker, fiscal_year);

-- ----------------------------------------------------------------------------
-- RAG: chunks con embeddings (tabla vectorial)
-- ticker / company / fiscal_year denormalizados sobre cada chunk para que el
-- pre-filtrado de pgvector no requiera JOIN con documents.
-- form_type / accounting_standard / canonical_section son metadata informativa
-- (NO filtros, ver contrato 1.2). chunk_index habilita expandir vecinos (3.4).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rag_chunks (
    id                  BIGSERIAL PRIMARY KEY,
    document_id         BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index         INT NOT NULL,
    content             TEXT NOT NULL,
    embedding           VECTOR(384) NOT NULL,
    ticker              TEXT NOT NULL,
    company             TEXT NOT NULL,
    fiscal_year         INT NOT NULL,
    form_type           TEXT,
    accounting_standard TEXT,
    canonical_section   TEXT,
    source_file         TEXT NOT NULL,
    page_start          INT,
    page_end            INT,
    numeric_density     REAL,
    -- True = confirmed folder company != cover-page registrant (excluded upstream
    -- at embedding time, should not normally appear here); False = confirmed
    -- match; NULL = unchecked, not "checked and fine" -- see rag/ingestion/RESULTS.md.
    -- Surfaced back out through search_similar()/retriever.py so an unverified
    -- (NULL) source can downgrade the response's confidence_flag instead of
    -- being silently trusted.
    company_name_mismatch BOOLEAN,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Migrations for columns added after a database may already exist.
-- CREATE TABLE IF NOT EXISTS above only helps on a genuinely fresh database --
-- against an already-existing rag_chunks table (e.g. anyone who ran init_db.sh
-- before 2026-08-11) it silently no-ops and the new column never gets added.
-- Confirmed real: this happened on the first run after company_name_mismatch
-- was added here. Every future column addition needs its own line below, not
-- just an edit to the CREATE TABLE block above.
-- ----------------------------------------------------------------------------
ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS company_name_mismatch BOOLEAN;

-- Busqueda por similitud de coseno (HNSW, aproximado)
CREATE INDEX IF NOT EXISTS idx_rag_chunks_hnsw
    ON rag_chunks USING hnsw (embedding vector_cosine_ops);

-- Pre-filtrado por metadata: ticker + fiscal_year (filtros confirmados)
CREATE INDEX IF NOT EXISTS idx_rag_chunks_ticker_year ON rag_chunks(ticker, fiscal_year);

-- Expansion de vecinos por chunk_index dentro de un documento (contrato 3.4)
CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_chunks(document_id, chunk_index);
