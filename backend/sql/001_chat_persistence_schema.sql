-- Chat persistence schema for PostgreSQL/Supabase
-- Safe to run multiple times.

CREATE TABLE IF NOT EXISTS conversations (
    id VARCHAR(128) PRIMARY KEY,
    user_id VARCHAR(128) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(128) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS message_sources (
    id BIGSERIAL PRIMARY KEY,
    message_id VARCHAR(36) NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    conversation_id VARCHAR(128) NOT NULL,
    chunk_id VARCHAR(256) NOT NULL,
    title VARCHAR(512) NOT NULL,
    company VARCHAR(128) NULL,
    ticker VARCHAR(64) NULL,
    fiscal_year INTEGER NULL,
    form_type VARCHAR(64) NULL,
    accounting_standard VARCHAR(64) NULL,
    canonical_section VARCHAR(128) NULL,
    source_file VARCHAR(512) NULL,
    page_start INTEGER NULL,
    page_end INTEGER NULL,
    relevance_score DOUBLE PRECISION NULL,
    text_snippet TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_feedback (
    feedback_id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(128) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_id VARCHAR(36) NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    rating VARCHAR(8) NOT NULL,
    reason TEXT NULL,
    user_id VARCHAR(128) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS ix_messages_role ON messages(role);
CREATE INDEX IF NOT EXISTS ix_messages_created_at ON messages(created_at);

CREATE INDEX IF NOT EXISTS ix_message_sources_message_id ON message_sources(message_id);
CREATE INDEX IF NOT EXISTS ix_message_sources_conversation_id ON message_sources(conversation_id);
CREATE INDEX IF NOT EXISTS ix_message_sources_chunk_id ON message_sources(chunk_id);
CREATE INDEX IF NOT EXISTS ix_message_sources_created_at ON message_sources(created_at);

CREATE INDEX IF NOT EXISTS ix_chat_feedback_conversation_id ON chat_feedback(conversation_id);
CREATE INDEX IF NOT EXISTS ix_chat_feedback_message_id ON chat_feedback(message_id);
CREATE INDEX IF NOT EXISTS ix_chat_feedback_rating ON chat_feedback(rating);
CREATE INDEX IF NOT EXISTS ix_chat_feedback_created_at ON chat_feedback(created_at);
