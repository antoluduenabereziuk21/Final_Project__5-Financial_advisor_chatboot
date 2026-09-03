"""Add the index the MATERIALIZED prefilter needs.

Without it, every filtered query seq-scans all 403,864 rows before the KNN
runs. The existing idx_rag_chunks_ticker_year is on (ticker, fiscal_year) and
can never be used: EntityResolver deliberately never emits a ticker filter.

    rag/.venv/Scripts/python.exe RAGAS/add_index.py
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
    print("creating idx_rag_chunks_company_year (may take a minute) ...")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rag_chunks_company_year "
        "ON rag_chunks (company, fiscal_year)")
    await conn.execute("ANALYZE rag_chunks")
    plan = await conn.fetch(
        "EXPLAIN SELECT id FROM rag_chunks WHERE company = ANY($1) AND fiscal_year = $2",
        ["amgen-inc"], 2021)
    print("\nplan for the prefilter:")
    for r in plan:
        print("  ", r[0])
    await conn.close()
    print("\ndone")

asyncio.run(main())
