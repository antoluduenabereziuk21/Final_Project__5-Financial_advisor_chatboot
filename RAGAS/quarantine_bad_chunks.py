"""Measure, and optionally remove, chunks whose text extraction failed.

    rag/.venv/Scripts/python.exe RAGAS/quarantine_bad_chunks.py            # report only
    rag/.venv/Scripts/python.exe RAGAS/quarantine_bad_chunks.py --apply    # delete

Background (2026-09-02). A retrieved chunk of 112,893 characters turned out
to be mojibake: a PDF subset font with no usable ToUnicode map, so extraction
emitted raw glyph codes. It was embedded and indexed like any other text --
nothing in ingestion checks whether extracted text is readable.

The giant chunks and the garbled chunks are the SAME documents, and that is
not a coincidence: garbled text has no sentence or paragraph structure, so
the splitter finds no boundaries and emits the whole document as one chunk.
The largest is 2,483,577 characters -- roughly 600k tokens, larger than any
context window, so retrieving it fails hard rather than degrading.

DETECTION. Two predicates, both deliberately conservative:

  cid_marker   content contains "(cid:"  -- the literal marker pdf extractors
               emit for a glyph they cannot map. No real 10-K contains it.

  no_english   a chunk over 1,000 chars containing NONE of " the ", " and ",
               " of ". Readable text always has these, including dense
               financial tables, whose row labels are English. This replaces
               the letter-ratio test, which flags legitimate numeric tables:
               a statements chunk is mostly digits and scores low on letters
               while being perfectly readable.

Oversized-but-readable chunks are reported separately and NOT deleted by
--apply. They are a chunking bug, not a text-extraction bug, and the fix is
re-chunking rather than removal.
"""
import asyncio
import os
import sys

import asyncpg

CID = "content LIKE '%(cid:%'"
NO_ENGLISH = ("length(content) > 1000 AND content NOT LIKE '% the %' "
              "AND content NOT LIKE '% and %' AND content NOT LIKE '% of %'")
BAD = f"(({CID}) OR ({NO_ENGLISH}))"


async def main(apply: bool):
    conn = await asyncpg.connect(
        host=os.getenv("VECTOR_DB_HOST", "localhost"),
        port=int(os.getenv("VECTOR_DB_PORT", "5432")),
        user=os.getenv("VECTOR_DB_USER", "ml_engineer"),
        password=os.getenv("VECTOR_DB_PASSWORD", "ml_password_2026"),
        database=os.getenv("VECTOR_DB_NAME", "financial_rag_vectors"),
        ssl=False,
    )

    tot_n = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks")
    tot_c = await conn.fetchval("SELECT SUM(length(content)) FROM rag_chunks")
    print(f"corpus: {tot_n:,} chunks, {tot_c:,} chars\n")

    print("=== how much is unreadable ===")
    for name, pred in (("(cid: marker", CID), ("no English stopwords", NO_ENGLISH),
                       ("either", BAD)):
        n = await conn.fetchval(f"SELECT COUNT(*) FROM rag_chunks WHERE {pred}")
        c = await conn.fetchval(
            f"SELECT COALESCE(SUM(length(content)),0) FROM rag_chunks WHERE {pred}")
        print(f"  {name:<22} {n:>7,} chunks ({100*n/tot_n:5.2f}%)   "
              f"{c:>13,} chars ({100*c/tot_c:5.2f}%)")

    print("\n=== oversized chunks: garbled vs readable ===")
    for label, extra in (("garbled", f"AND {BAD}"), ("READABLE", f"AND NOT {BAD}")):
        r = await conn.fetchrow(
            f"SELECT COUNT(*) n, COALESCE(MAX(length(content)),0) mx "
            f"FROM rag_chunks WHERE length(content) > 20000 {extra}")
        print(f"  >20k chars, {label:<9}: {r['n']:>6,} chunks, largest {r['mx']:,}")
    print("  (readable oversized chunks are a CHUNKING bug -- re-chunk, do not delete)")

    print("\n=== documents most affected ===")
    for r in await conn.fetch(f"""
        SELECT ticker, company, fiscal_year, COUNT(*) n, SUM(length(content)) c
        FROM rag_chunks WHERE {BAD}
        GROUP BY ticker, company, fiscal_year ORDER BY c DESC LIMIT 15"""):
        print(f"  {r['n']:>5} chunks {r['c']:>11,} chars  {r['ticker'] or '?':<6} "
              f"{r['company']:<38} FY{r['fiscal_year']}")

    print("\n=== documents that would be left with NOTHING ===")
    gone = await conn.fetch(f"""
        SELECT ticker, company, fiscal_year, COUNT(*) n
        FROM rag_chunks GROUP BY ticker, company, fiscal_year
        HAVING COUNT(*) FILTER (WHERE NOT {BAD}) = 0 ORDER BY 2, 3""")
    for r in gone:
        print(f"  {r['ticker'] or '?':<6} {r['company']:<38} FY{r['fiscal_year']} "
              f"({r['n']} chunks, all unreadable)")
    print(f"  {len(gone)} document(s) would disappear from the index entirely")

    print("\n=== eval-set companies affected ===")
    try:
        import csv
        from pathlib import Path
        qs = list(csv.DictReader(
            open(Path(__file__).parent / "eval_questions_v2.csv", encoding="utf-8")))
        want = {(r["company"], r["fiscal_year"]) for r in qs if r["company"]}
        for co, fy in sorted(want):
            if not fy:
                continue
            n = await conn.fetchval(
                f"SELECT COUNT(*) FROM rag_chunks WHERE company=$1 AND fiscal_year=$2 "
                f"AND {BAD}", co, int(float(fy)))
            ok = await conn.fetchval(
                f"SELECT COUNT(*) FROM rag_chunks WHERE company=$1 AND fiscal_year=$2 "
                f"AND NOT {BAD}", co, int(float(fy)))
            if n:
                print(f"  {co:<40} FY{int(float(fy))}: {n} unreadable / {ok} readable")
    except Exception as exc:
        print("  (could not read eval_questions_v2.csv:", exc, ")")

    if not apply:
        print("\nREPORT ONLY. Re-run with --apply to delete the unreadable chunks.")
        print("Deletion is not reversible without re-ingesting those PDFs.")
    else:
        n = await conn.fetchval(f"SELECT COUNT(*) FROM rag_chunks WHERE {BAD}")
        print(f"\ndeleting {n:,} unreadable chunks ...")
        await conn.execute(f"DELETE FROM rag_chunks WHERE {BAD}")
        await conn.execute("ANALYZE rag_chunks")
        left = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks")
        print(f"done. {left:,} chunks remain.")
        print("NOTE: the HNSW index still holds the deleted vectors until it is "
              "rebuilt or vacuumed. Run: VACUUM ANALYZE rag_chunks;")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
