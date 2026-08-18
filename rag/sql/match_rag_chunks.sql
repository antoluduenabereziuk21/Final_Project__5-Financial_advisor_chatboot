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
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
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
        1 - (rc.embedding <=> query_embedding) AS similarity
    FROM public.rag_chunks AS rc
    WHERE
        (
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
    ORDER BY rc.embedding <=> query_embedding
    LIMIT LEAST(GREATEST(match_count, 1), 20);
$$;
