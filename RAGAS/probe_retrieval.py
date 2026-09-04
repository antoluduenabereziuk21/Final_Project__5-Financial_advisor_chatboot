"""
Why does a correct company+fiscal_year filter return zero chunks?

29 rows in the 2026-09-02 pipeline run resolved to a (company, fiscal_year)
pair that provably exists in rag_chunks, passed no ticker filter, hit a query
with no similarity threshold -- and got back nothing. 28 structurally
identical rows worked. This isolates which layer drops them.

    rag/.venv/Scripts/python.exe RAGAS/probe_retrieval.py
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import asyncpg

# (company, fiscal_year, question that failed)
FAILING = [
    ("amgen-inc", 2021, "What was AMGN's research and development expense in fiscal 2021?"),
    ("aemetis-inc", 2017, "What was Aemetis's research and development expense in fiscal 2017?"),
    ("atyr-pharma-inc", 2020, "What was LIFE's net loss in fiscal 2020?"),
    ("apple-inc", None, "Should I invest in Apple?"),
]

DSN = dict(
    host=os.getenv("VECTOR_DB_HOST", "localhost"),
    port=int(os.getenv("VECTOR_DB_PORT", "5432")),
    user=os.getenv("VECTOR_DB_USER", "ml_engineer"),
    password=os.getenv("VECTOR_DB_PASSWORD", "ml_password_2026"),
    database=os.getenv("VECTOR_DB_NAME", "financial_rag_vectors"),
)


async def main():
    print(f"connecting to {DSN['user']}@{DSN['host']}:{DSN['port']}/{DSN['database']}")
    conn = await asyncpg.connect(ssl=False, **DSN)

    print("\n=== LAYER 0: which ANN index is doing this ===")
    for r in await conn.fetch(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename='rag_chunks'"):
        print("  ", r["indexname"], "::", r["indexdef"][:150])
    for gucs in ("ivfflat.probes", "hnsw.ef_search"):
        try:
            print("  ", gucs, "=", await conn.fetchval(f"SHOW {gucs}"))
        except Exception:
            print("  ", gucs, "= (not set / extension not loaded)")

    print("\n=== LAYER 1: does the row exist at all (no vector involved) ===")
    for co, fy, _ in FAILING:
        n_co = await conn.fetchval(
            "SELECT COUNT(*) FROM rag_chunks WHERE company = ANY($1)", [co])
        n_any = await conn.fetchval(
            "SELECT COUNT(*) FROM rag_chunks WHERE company = $1", co)
        n_fy = ("-" if fy is None else await conn.fetchval(
            "SELECT COUNT(*) FROM rag_chunks WHERE company = ANY($1) "
            "AND fiscal_year = $2", [co], fy))
        n_emb = await conn.fetchval(
            "SELECT COUNT(*) FROM rag_chunks WHERE company = ANY($1) "
            "AND embedding IS NOT NULL", [co])
        print(f"  {co:<36} = ANY:{n_co:<7} = scalar:{n_any:<7} +fy:{str(n_fy):<7} "
              f"non-null embedding:{n_emb}")

    print("\n=== LAYER 2: the exact SQL search_similar builds ===")
    vec = "[" + ",".join(["0.01"] * 384) + "]"
    for co, fy, _ in FAILING:
        if fy is None:
            sql = ("SELECT id, company, fiscal_year FROM rag_chunks WHERE company = ANY($2) "
                   "ORDER BY embedding <=> $1::vector LIMIT $3")
            args = (vec, [co], 5)
        else:
            sql = ("SELECT id, company, fiscal_year FROM rag_chunks WHERE company = ANY($2) "
                   "AND fiscal_year = $3 ORDER BY embedding <=> $1::vector LIMIT $4")
            args = (vec, [co], fy, 5)
        try:
            rows = await conn.fetch(sql, *args)
            print(f"  {co:<36} fy={fy}  -> {len(rows)} rows "
                  f"{[ (r['company'], r['fiscal_year']) for r in rows[:2] ]}")
        except Exception as exc:
            print(f"  {co:<36} fy={fy}  -> SQL ERROR {type(exc).__name__}: {exc}")

    print("\n=== LAYER 3: fiscal_year column type / stray values ===")
    t = await conn.fetchval("""SELECT data_type FROM information_schema.columns
                               WHERE table_name='rag_chunks' AND column_name='fiscal_year'""")
    print("  fiscal_year data_type:", t)
    for co, fy, _ in FAILING:
        yrs = await conn.fetch(
            "SELECT DISTINCT fiscal_year FROM rag_chunks WHERE company = ANY($1) "
            "ORDER BY 1", [co])
        print(f"  {co:<36} years present: {[r['fiscal_year'] for r in yrs]}")

    await conn.close()

    print("\n=== LAYER 4: the app path, end to end ===")
    try:
        from rag.embeddings.generate import embed_text
        from rag.vector_store.client import VectorDbClient
        from rag.vector_store.repository import VectorRepository
        from rag.retrieval.retriever import retrieve
    except Exception as exc:
        print("  could not import the app path:", exc)
        return

    client = VectorDbClient(**DSN)
    await client.connect()
    repo = VectorRepository(client)
    for co, fy, question in FAILING:
        emb = embed_text(question)
        print(f"  embed_text -> dim={len(emb)} first3={[round(x, 4) for x in emb[:3]]}")
        sources, meta = await retrieve(repo, question, ticker=None, company=[co],
                                       fiscal_year=fy, top_k=5)
        print(f"  {co:<36} fy={fy} -> {len(sources)} sources  meta={meta}")
        if sources:
            s = sources[0]
            print(f"      top: {s.get('company')} FY{s.get('fiscal_year')} "
                  f"score={s.get('relevance_score')}")
        # same question, no filters at all, for contrast
        s2, _ = await retrieve(repo, question, top_k=5)
        print(f"      unfiltered same question -> {len(s2)} sources"
              + (f", top company={s2[0].get('company')}" if s2 else ""))


if __name__ == "__main__":
    asyncio.run(main())
