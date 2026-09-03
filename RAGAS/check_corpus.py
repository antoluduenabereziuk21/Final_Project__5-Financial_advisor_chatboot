"""
Quick corpus-coverage check against the local Postgres/pgvector instance.
Run with the same interpreter that has asyncpg installed (rag/.venv):

    rag\\.venv\\Scripts\\python.exe RAGAS\\check_corpus.py

Reads connection params from env vars, same names/defaults as docker/docker-compose.yml,
so it works out of the box against the local container without hardcoding secrets here.
"""
import asyncio
import os
from collections import Counter

import asyncpg


async def main():
    conn = await asyncpg.connect(
        host=os.getenv("VECTOR_DB_HOST", "localhost"),
        port=int(os.getenv("VECTOR_DB_PORT", "5432")),
        user=os.getenv("VECTOR_DB_USER", "ml_engineer"),
        password=os.getenv("VECTOR_DB_PASSWORD", "ml_password_2026"),
        database=os.getenv("VECTOR_DB_NAME", "financial_rag_vectors"),
        ssl=False,  # local docker postgres has no SSL configured; asyncpg's default
        # SSL-negotiation attempt against a plain server is what causes the
        # "unexpected connection_lost() call" error on Windows.
    )

    total_chunks = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks")
    total_docs = await conn.fetchval("SELECT COUNT(*) FROM documents")
    print(f"rag_chunks rows: {total_chunks}")
    print(f"documents rows:  {total_docs}")

    rows = await conn.fetch("SELECT DISTINCT ticker, company, fiscal_year FROM documents ORDER BY company, fiscal_year")
    print(f"\ndistinct (ticker, company, fiscal_year) combos: {len(rows)}")

    first_letters = Counter((r["company"] or "?")[0].upper() for r in rows)
    print("\ncompany first-letter distribution:")
    for letter in sorted(first_letters):
        print(f"  {letter}: {first_letters[letter]}")

    print("\nfirst 20 rows:")
    for r in rows[:20]:
        print(f"  {r['ticker']!s:6} {r['company']:40} FY{r['fiscal_year']}")

    with open("RAGAS/corpus_companies.csv", "w", encoding="utf-8") as f:
        f.write("ticker,company,fiscal_year\n")
        for r in rows:
            f.write(f"{r['ticker'] or ''},{r['company'] or ''},{r['fiscal_year'] or ''}\n")
    print("\nWrote full list to RAGAS/corpus_companies.csv")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
