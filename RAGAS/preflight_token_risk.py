"""Worst-case prompt size per eval question, before spending any credits.

For every question, look at the chunks its filter can actually reach and sum
the 5 largest -- that is the biggest context the generator could be handed.
Reports with and without the RAG_MAX_CHUNK_CHARS cap so you can see what the
cap is buying.

    rag/.venv/Scripts/python.exe RAGAS/preflight_token_risk.py
"""
import asyncio, csv, os
from pathlib import Path
import asyncpg

TOP_K = 5
CAP = int(os.getenv("RAG_MAX_CHUNK_CHARS", "20000"))
CHARS_PER_TOKEN = 4.0   # rough for English; fine for an order-of-magnitude check

async def main():
    conn = await asyncpg.connect(
        host=os.getenv("VECTOR_DB_HOST", "localhost"),
        port=int(os.getenv("VECTOR_DB_PORT", "5432")),
        user=os.getenv("VECTOR_DB_USER", "ml_engineer"),
        password=os.getenv("VECTOR_DB_PASSWORD", "ml_password_2026"),
        database=os.getenv("VECTOR_DB_NAME", "financial_rag_vectors"),
        ssl=False)

    rows = list(csv.DictReader(
        open(Path(__file__).parent / "eval_questions_v2.csv", encoding="utf-8")))

    async def top5(co, fy, cap):
        where, args = [], []
        if co:
            args.append(co); where.append(f"company = ${len(args)}")
        if fy:
            args.append(int(float(fy))); where.append(f"fiscal_year = ${len(args)}")
        if cap:
            args.append(cap); where.append(f"length(content) < ${len(args)}")
        sql = ("SELECT length(content) n FROM rag_chunks"
               + (" WHERE " + " AND ".join(where) if where else "")
               + f" ORDER BY n DESC LIMIT {TOP_K}")
        return [r["n"] for r in await conn.fetch(sql, *args)]

    print(f"{'id':>3} {'category':<28} {'company':<34} {'uncapped':>10} {'capped':>9}")
    worst_u = worst_c = 0
    flagged = []
    for r in rows:
        co, fy = r["company"], r["fiscal_year"]
        u = sum(await top5(co, fy, 0))
        c = sum(await top5(co, fy, CAP))
        worst_u, worst_c = max(worst_u, u), max(worst_c, c)
        if u > 60000:
            flagged.append((r["id"], r["category"], co or "(no filter)", u, c))
        print(f"{r['id']:>3} {r['category']:<28} {(co or '(unfiltered)'):<34} "
              f"{u:>10,} {c:>9,}")

    print(f"\ncap = {CAP:,} chars")
    print(f"worst-case context  uncapped: {worst_u:>10,} chars "
          f"(~{worst_u/CHARS_PER_TOKEN:,.0f} tokens)")
    print(f"worst-case context    capped: {worst_c:>10,} chars "
          f"(~{worst_c/CHARS_PER_TOKEN:,.0f} tokens)")
    print(f"\nquestions whose UNCAPPED worst case exceeds 60,000 chars: {len(flagged)}")
    for f in flagged:
        print(f"  [{f[0]}] {f[1]:<26} {f[2]:<34} {f[3]:>10,} -> {f[4]:>8,}")
    await conn.close()

asyncio.run(main())
