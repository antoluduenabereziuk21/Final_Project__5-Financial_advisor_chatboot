-- match_rag_chunks — filtered ANN search over rag_chunks.
--
-- FIX 2026-09-03: filter BEFORE the ANN scan.
--
-- The previous version was:
--
--     SELECT ... FROM public.rag_chunks AS rc
--     WHERE (filter_ticker IS NULL OR rc.ticker = ANY(filter_ticker))
--       AND (filter_company IS NULL OR rc.company = ANY(filter_company))
--       AND (filter_fiscal_year IS NULL OR rc.fiscal_year = filter_fiscal_year)
--     ORDER BY rc.embedding <=> query_embedding
--     LIMIT ...
--
-- That returns ZERO ROWS for almost every filtered query. rag_chunks carries
-- an HNSW index (vector_cosine_ops). Postgres scans the ANN index FIRST,
-- gets back hnsw.ef_search (default 40) nearest neighbours across the whole
-- table, and only THEN applies the WHERE clause to those 40 survivors. A
-- company that owns a few hundred of 400k chunks essentially never appears in
-- the global top 40, so the filter discards all 40 and the query returns
-- nothing — while the matching rows sit untouched in the table.
--
-- Measured on the local mirror of this schema (2026-09-02):
--   WHERE company='amgen-inc' AND fiscal_year=2021             -> 276 rows
--   ...same, plus ORDER BY embedding <=> $1 LIMIT 5            ->   0 rows
--
-- An ORDER BY cannot remove rows. An ANN index scan can.
--
-- The fix is the MATERIALIZED CTE below: it forces the filter to be evaluated
-- first, so the KNN runs over the filtered subset only. That makes it an
-- EXACT nearest-neighbour search rather than an approximate one, which is
-- both more correct and cheap here — a company+year filter leaves a few
-- hundred rows, not hundreds of thousands.
--
-- The unfiltered branch is kept separate and deliberately does NOT use the
-- CTE: materialising 400k rows to run exact KNN would turn every open-ended
-- question into a full scan. Unfiltered queries should use the ANN index,
-- which is what it is for.
--
-- Language changes from `sql` to `plpgsql` because that branch has to be
-- chosen at runtime.
--
-- Companion index (the prefilter otherwise sequential-scans the table):
--   CREATE INDEX IF NOT EXISTS idx_rag_chunks_company_year
--       ON public.rag_chunks (company, fiscal_year);
--   ANALYZE public.rag_chunks;
--
-- NOTE: the pre-existing idx_rag_chunks_ticker_year is on (ticker,
-- fiscal_year). EntityResolver never emits a ticker filter, so that index has
-- never been used by this function and cannot be.

CREATE OR REPLACE FUNCTION public.match_rag_chunks(
    query_embedding public.vector(384),
    match_count integer DEFAULT 5,
    filter_ticker text[] DEFAULT NULL,
    filter_company text[] DEFAULT NULL,
    filter_fiscal_year integer DEFAULT NULL
)
RETURNS TABLE (
    id bigint,
    document_id bigint,
    chunk_index integer,
    content text,
    ticker text,
    company text,
    fiscal_year integer,
    form_type text,
    accounting_standard text,
    canonical_section text,
    source_file text,
    page_start integer,
    page_end integer,
    numeric_density real,
    company_name_mismatch boolean,
    similarity double precision
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    -- Clamp identical to the original: at least 1, at most 20.
    v_limit integer := LEAST(GREATEST(match_count, 1), 20);

    -- Skip chunks whose text extraction failed. Those documents produced no
    -- sentence boundaries, so the splitter emitted them whole: 1,544 chunks
    -- over 20,000 chars, the largest 2,483,577 (~600k tokens, past any
    -- context window). Retrieving one costs an entire provider daily budget
    -- in a single call. Median chunk is 2,494 chars and the distribution is
    -- bimodal with an empty band between 19,771 and 20,276, so this cut
    -- removes only the broken tail.
    v_max_chars integer := 20000;
BEGIN
    IF filter_ticker IS NULL
       AND filter_company IS NULL
       AND filter_fiscal_year IS NULL
    THEN
        -- No filters: let the HNSW index do its job.
        RETURN QUERY
        SELECT
            rc.id,
            rc.document_id,
            rc.chunk_index,
            rc.content,
            rc.ticker,
            rc.company,
            rc.fiscal_year,
            rc.form_type,
            rc.accounting_standard,
            rc.canonical_section,
            rc.source_file,
            rc.page_start,
            rc.page_end,
            rc.numeric_density,
            rc.company_name_mismatch,
            (1 - (rc.embedding <=> query_embedding))::double precision AS similarity
        FROM public.rag_chunks AS rc
        WHERE length(rc.content) < v_max_chars
        ORDER BY rc.embedding <=> query_embedding
        LIMIT v_limit;
    ELSE
        -- Filtered: evaluate the filter first, then KNN over that subset.
        RETURN QUERY
        WITH filtered AS MATERIALIZED (
            SELECT rc.*
            FROM public.rag_chunks AS rc
            WHERE (
                filter_ticker IS NULL
                OR rc.ticker = ANY(filter_ticker)
            )
            AND (
                filter_company IS NULL
                OR rc.company = ANY(filter_company)
            )
            AND (
                filter_fiscal_year IS NULL
                OR rc.fiscal_year = filter_fiscal_year
            )
            AND length(rc.content) < v_max_chars
        )
        SELECT
            f.id,
            f.document_id,
            f.chunk_index,
            f.content,
            f.ticker,
            f.company,
            f.fiscal_year,
            f.form_type,
            f.accounting_standard,
            f.canonical_section,
            f.source_file,
            f.page_start,
            f.page_end,
            f.numeric_density,
            f.company_name_mismatch,
            (1 - (f.embedding <=> query_embedding))::double precision AS similarity
        FROM filtered AS f
        ORDER BY f.embedding <=> query_embedding
        LIMIT v_limit;
    END IF;
END;
$$;
