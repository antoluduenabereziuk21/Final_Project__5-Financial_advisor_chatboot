"""Identify the oversized chunk, and measure how much of the corpus is
failed PDF text extraction.

A 112,893-char chunk retrieved on 2026-09-02 turned out to be mojibake: a
subset font with no usable ToUnicode map, so extraction emitted raw glyph
codes ("(cid:127)" markers, letters substituted one-for-one). It was
embedded and indexed like any other text. Nothing in ingestion checks
whether extracted text is readable.

    rag/.venv/Scripts/python.exe RAGAS/find_bad_chunks.py
"""
import asyncio, os, asyncpg

async def main():
    conn = await asyncpg.connect(
        host=os.getenv("VECTOR_DB_HOST", "localhost"),
        port=int(os.getenv("VECTOR_DB_PORT", "5432")),
        user=os.getenv("VECTOR_DB_USER", "ml_engineer"),
        password=os.getenv("VECTOR_DB_PASSWORD", "ml_password_2026"),
        database=os.getenv("VECTOR_DB_NAME", "financial_rag_vectors"),
        ssl=False,
    )

    print("=== chunk length distribution ===")
    for r in await conn.fetch("""
        SELECT width_bucket(length(content), 0, 20000, 10) b,
               COUNT(*) n, MIN(length(content)) lo, MAX(length(content)) hi
        FROM rag_chunks GROUP BY b ORDER BY b"""):
        print(f"  bucket {r['b']:>2}: {r['n']:>7} chunks  ({r['lo']}-{r['hi']} chars)")

    print("\n=== chunks over 20,000 chars ===")
    rows = await conn.fetch("""
        SELECT id, ticker, company, fiscal_year, source_file, length(content) len
        FROM rag_chunks WHERE length(content) > 20000
        ORDER BY len DESC LIMIT 40""")
    for r in rows:
        print(f"  {r['len']:>8}  {r['ticker'] or '?':<6} {r['company']:<38} "
              f"FY{r['fiscal_year']}  {(r['source_file'] or '')[-48:]}")
    print(f"  ({len(rows)} shown)")

    print("\n=== failed font extraction: chunks containing '(cid:' ===")
    n = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks WHERE content LIKE '%(cid:%'")
    tot = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks")
    print(f"  {n} of {tot} chunks ({100.0*n/max(tot,1):.2f}%)")
    for r in await conn.fetch("""
        SELECT ticker, company, fiscal_year, COUNT(*) n, SUM(length(content)) chars
        FROM rag_chunks WHERE content LIKE '%(cid:%'
        GROUP BY ticker, company, fiscal_year ORDER BY chars DESC LIMIT 25"""):
        print(f"  {r['n']:>5} chunks  {r['chars']:>9} chars  {r['ticker'] or '?':<6} "
              f"{r['company']:<38} FY{r['fiscal_year']}")

    # Readable English text is mostly ASCII letters and spaces. Mojibake is
    # not. This catches garbled documents that carry no "(cid:" marker.
    print("\n=== low letter-ratio chunks (mojibake without a (cid: marker) ===")
    for r in await conn.fetch("""
        SELECT ticker, company, fiscal_year, COUNT(*) n
        FROM rag_chunks
        WHERE length(content) > 500
          AND length(regexp_replace(content, '[^A-Za-z ]', '', 'g'))::float
              / length(content) < 0.55
          AND content NOT LIKE '%(cid:%'
        GROUP BY ticker, company, fiscal_year ORDER BY n DESC LIMIT 20"""):
        print(f"  {r['n']:>5} chunks  {r['ticker'] or '?':<6} {r['company']:<38} FY{r['fiscal_year']}")

    await conn.close()

asyncio.run(main())
