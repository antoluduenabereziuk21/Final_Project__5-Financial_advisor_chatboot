"""
Build eval_questions_v2.csv from the corpus that is ACTUALLY in the local index.

Why this exists: eval_questions_v1.csv was written against a file list, not
against chunk content. Against the active index that made 45 of 70 questions
unanswerable and their ground-truth strings unverifiable. Every fact row this
script emits is extracted from a chunk that is in the index, and carries the
source line it came from, so the ground truth is auditable.

Run it with the same interpreter that has asyncpg (rag/.venv), from the repo root:

    rag\\.venv\\Scripts\\python.exe RAGAS\\build_eval_questions_v2.py

Outputs, all under RAGAS/:
    preflight_report.txt        corpus health: doc/chunk counts, embedding dim,
                                ticker completeness, section + year distribution
    corpus_inventory.csv        every (ticker, company, fiscal_year, form_type)
    eval_fact_candidates.csv    every extracted figure + the source line
    eval_questions_v2.csv       the question set (same header as v1)

It prints a compact summary at the end. Nothing here calls an LLM.
"""
from __future__ import annotations

import asyncio
import csv
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import asyncpg

HERE = Path(__file__).resolve().parent
SEED = 20260902
random.seed(SEED)

# Target shape. 500 judge requests/day / 9 calls per row => ~55 scored rows is
# the hard ceiling for a one-day run. Behavioural rows cost 0 judge calls.
N_SCORED_TARGET = 50
MAX_A_SHARE = 0.40  # 248 of 444 tickers start with A; cap them at 40% of the set

# ---------------------------------------------------------------- extraction

# Canonical statement-line labels. Matching is EXACT against the whole
# non-numeric prefix of the line, not a prefix match: "Net loss from disposal
# of subsidiaries" and "Net income (loss) before income taxes" are different
# line items and must not be harvested as "net loss" / "net income".
LABEL_ALIASES = {
    "total assets": "total assets",
    "total liabilities": "total liabilities",
    "net income": "net income",
    "net income loss": "net income",
    "net loss": "net loss",
    "net loss income": "net loss",
    "total revenue": "total revenue",
    "total revenues": "total revenue",
    "total net revenue": "total revenue",
    "total net revenues": "total revenue",
    "net revenues": "total revenue",
    "total net sales": "total net sales",
    "net sales": "total net sales",
    "research and development": "research and development expense",
    "research and development expense": "research and development expense",
    "research and development expenses": "research and development expense",
    "cash and cash equivalents": "cash and cash equivalents",
    "total stockholders equity": "total stockholders' equity",
    "total shareholders equity": "total stockholders' equity",
    "total operating expenses": "total operating expenses",
    "gross profit": "gross profit",
}

# One numeric column. Handles $ prefixes, thousands separators, decimals,
# parenthesised negatives, and BARE integers -- the omission of bare integers
# was the bug that made column position meaningless (a row reading
# "246 2,367" was read as a single-column row holding 2,367).
_NUM = r"\$?\s*\(?\s*\d[\d,]*(?:\.\d+)?\s*\)?"
# A placeholder column: em dash, en dash, hyphen, or "n/a".
_DASH = r"(?:[—–-]+|n/?a)"
_COL = rf"(?:{_NUM}|{_DASH})"
_LINE = re.compile(
    rf"^(?P<label>[A-Za-z][A-Za-z'’()&/,.\s-]{{2,60}}?)\s*[:.]?\s*"
    rf"(?P<cols>{_COL}(?:\s+{_COL}){{0,7}})\s*$"
)
_NUM_RE = re.compile(_NUM)
_DASH_RE = re.compile(rf"^{_DASH}$")

# Lines that are ratios, per-share amounts or percentages are not the
# statement lines these questions are about.
_REJECT_IN_LINE = re.compile(r"per share|per diluted|%|percent", re.I)


def _norm_label(raw: str) -> str:
    t = raw.lower().replace("’", "").replace("'", "")
    t = re.sub(r"[(),.&/-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _split_cols(cols: str) -> list[str]:
    return re.findall(rf"{_COL}", cols)


def extract_facts(content: str) -> list[dict]:
    """Pull (label, value, source_line) triples out of one chunk.

    Two rules do the work:

    1. The label must match a canonical statement line EXACTLY once the
       non-numeric prefix is normalised. Prefix matching harvested
       "Net income (loss) before income taxes" as net income.
    2. Every column is parsed, including bare integers and dash
       placeholders, so the FIRST column really is the first column. In a
       10-K the columns run most-recent-year first, so column 1 is the
       document's own fiscal year -- but only if column 1 was actually seen.

    A line whose first column is a dash placeholder is dropped: the current
    year has no value on it, so there is nothing to ask about.
    """
    out = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if len(line) < 10 or len(line) > 320 or _REJECT_IN_LINE.search(line):
            continue
        m = _LINE.match(line)
        if not m:
            continue
        label = LABEL_ALIASES.get(_norm_label(m.group("label")))
        if not label:
            continue
        cols = _split_cols(m.group("cols"))
        if not cols or len(cols) > 6:
            continue
        first = cols[0].strip()
        if _DASH_RE.match(first):
            continue
        digits = re.sub(r"[^\d]", "", first)
        if len(digits) < 3:          # footnote markers, "1", "12"
            continue
        value = re.sub(r"\s+", "", first)
        out.append({
            "label": label,
            "value": value,
            "n_figures": len(cols),
            "source_line": line,
        })
    return out


def validate(cands: list[dict]) -> tuple[list[dict], list[str]]:
    """Drop candidates that cannot be trusted as year-specific ground truth.

    The failure this exists to stop: two different fiscal years of the same
    company yielding the SAME value for the same label. That means column 1
    was not the current year on at least one of them, and a
    fiscal_year_discrimination pair built from them tests nothing. Seen for
    real on Aemetis R&D (FY2017 and FY2018 both reported 2,367) in the first
    generated set.
    """
    by_key = defaultdict(list)
    for c in cands:
        by_key[(c["company"], c["label"])].append(c)

    keep, notes = [], []
    dropped_dupe = 0
    for (co, label), group in by_key.items():
        seen = defaultdict(list)
        for c in group:
            seen[c["value"]].append(c["fiscal_year"])
        bad_values = {v for v, yrs in seen.items() if len(set(yrs)) > 1}
        for c in group:
            if c["value"] in bad_values:
                dropped_dupe += 1
                continue
            keep.append(c)
    notes.append(f"dropped {dropped_dupe} candidates whose value repeats across "
                 f"fiscal years for the same company+label")
    return keep, notes


# ---------------------------------------------------------------- db access

async def fetch(conn, sql, *args):
    return await conn.fetch(sql, *args)


async def load_corpus(conn):
    inventory = await fetch(conn, """
        SELECT ticker, company, fiscal_year, form_type,
               COUNT(*) AS n_chunks,
               MAX(accounting_standard) AS accounting_standard,
               BOOL_OR(company_name_mismatch IS NULL) AS has_unverified
        FROM rag_chunks
        GROUP BY ticker, company, fiscal_year, form_type
        ORDER BY company, fiscal_year
    """)
    # One high-numeric-density chunk per (company, fiscal_year): the densest
    # chunk is nearly always a financial statement or MD&A table.
    chunks = await fetch(conn, """
        SELECT DISTINCT ON (company, fiscal_year)
               ticker, company, fiscal_year, form_type, canonical_section, content
        FROM rag_chunks
        WHERE content ~* '(total assets|net income|net loss|total revenue|total net sales)'
        ORDER BY company, fiscal_year, numeric_density DESC NULLS LAST
    """)
    return inventory, chunks


async def preflight(conn) -> list[str]:
    L = []
    docs = await conn.fetchval("SELECT COUNT(*) FROM documents")
    chunks = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks")
    tickers = await conn.fetchval("SELECT COUNT(DISTINCT ticker) FROM rag_chunks")
    companies = await conn.fetchval("SELECT COUNT(DISTINCT company) FROM rag_chunks")
    L.append(f"documents rows        : {docs}      (expected ~1774)")
    L.append(f"rag_chunks rows       : {chunks}   (expected ~406011)")
    L.append(f"distinct tickers      : {tickers}     (expected 444)")
    L.append(f"distinct companies    : {companies}")
    try:
        dim = await conn.fetchval("SELECT vector_dims(embedding) FROM rag_chunks LIMIT 1")
        flag = "OK" if dim == 384 else "MISMATCH -- match_rag_chunks expects vector(384)"
        L.append(f"embedding dimension   : {dim}  [{flag}]")
    except Exception as exc:
        L.append(f"embedding dimension   : could not read ({exc})")
    null_tk = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks WHERE ticker IS NULL")
    L.append(f"chunks with NULL ticker: {null_tk}")
    unver = await conn.fetchval(
        "SELECT COUNT(*) FROM rag_chunks WHERE company_name_mismatch IS NULL")
    L.append(f"chunks unverified attr : {unver} ({100.0*unver/max(chunks,1):.1f}%)")
    years = await fetch(conn, """
        SELECT fiscal_year, COUNT(DISTINCT company) c FROM rag_chunks
        GROUP BY fiscal_year ORDER BY fiscal_year""")
    L.append("fiscal years (companies): " +
             ", ".join(f"{r['fiscal_year']}:{r['c']}" for r in years))
    secs = await fetch(conn, """
        SELECT canonical_section, COUNT(*) c FROM rag_chunks
        GROUP BY canonical_section ORDER BY c DESC LIMIT 12""")
    L.append("top canonical_sections  : " +
             ", ".join(f"{r['canonical_section']}:{r['c']}" for r in secs))
    return L


# ---------------------------------------------------------------- selection

def stratified_pick(cands: list[dict], n: int) -> list[dict]:
    """Spread picks across ticker first-letter and fiscal year, and cap the
    A bucket. 248 of 444 tickers start with A, so an unweighted sample is
    ~56% A and makes the set look like it only covers one letter."""
    by_letter = defaultdict(list)
    for c in cands:
        by_letter[(c["ticker"] or c["company"])[0].upper()].append(c)
    for v in by_letter.values():
        random.shuffle(v)

    max_a = int(n * MAX_A_SHARE)
    picked, used_company = [], set()
    letters = sorted(by_letter)
    # Round-robin across letters so every represented letter gets a turn
    # before any letter gets a second row.
    while len(picked) < n and any(by_letter.values()):
        progressed = False
        for L in letters:
            if len(picked) >= n:
                break
            bucket = by_letter[L]
            if L == "A" and sum(1 for p in picked
                                if (p["ticker"] or p["company"])[0].upper() == "A") >= max_a:
                continue
            while bucket:
                c = bucket.pop()
                if c["company"] in used_company:
                    continue
                picked.append(c)
                used_company.add(c["company"])
                progressed = True
                break
        if not progressed:
            break
    return picked


def find_confusable_pairs(companies: list[str]) -> list[tuple[str, str]]:
    """Companies sharing their first name token -- the real disambiguation
    hazard in this corpus (applied-materials vs applied-optoelectronics)."""
    by_head = defaultdict(list)
    for c in companies:
        head = re.split(r"[-_ ]", c)[0].lower()
        if len(head) >= 4:
            by_head[head].append(c)
    pairs = []
    for head, group in sorted(by_head.items()):
        if len(group) >= 2:
            g = sorted(set(group))
            pairs.append((g[0], g[1]))
    return pairs


def pretty(company: str) -> str:
    """Slug -> the name a person would type."""
    words = re.split(r"[-_]", company)
    drop = {"inc", "corp", "corporation", "incorporated", "company", "co",
            "ltd", "limited", "plc", "llc", "lp", "holdings", "holding", "group"}
    core = [w for w in words if w.lower() not in drop] or words
    out = " ".join(w.capitalize() if not w.isupper() else w for w in core)
    # A slug that reduces to a digit stub ("9f") is not a usable company name
    # in a question; fall back to the full slug spelled out.
    if len(out) < 4 or not re.search(r"[A-Za-z]{3}", out):
        out = " ".join(w.capitalize() for w in words)
    return out


def typo(name: str) -> str:
    """One deterministic character-level corruption, not a random one, so the
    set is reproducible."""
    parts = name.split()
    w = max(parts, key=len)
    i = len(w) // 2
    return name.replace(w, w[:i] + w[i + 1:], 1) if len(w) > 4 else name + "e"


# ---------------------------------------------------------------- main

async def main():
    conn = await asyncpg.connect(
        host=os.getenv("VECTOR_DB_HOST", "localhost"),
        port=int(os.getenv("VECTOR_DB_PORT", "5432")),
        user=os.getenv("VECTOR_DB_USER", "ml_engineer"),
        password=os.getenv("VECTOR_DB_PASSWORD", "ml_password_2026"),
        database=os.getenv("VECTOR_DB_NAME", "financial_rag_vectors"),
        ssl=False,
    )
    print("connected; running preflight ...")
    report = await preflight(conn)
    print("\n".join(report))
    (HERE / "preflight_report.txt").write_text("\n".join(report), encoding="utf-8")

    print("\nloading inventory + candidate chunks (this takes a minute) ...")
    inventory, chunks = await load_corpus(conn)
    await conn.close()

    with open(HERE / "corpus_inventory.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "company", "fiscal_year", "form_type", "n_chunks",
                    "accounting_standard", "has_unverified_attribution"])
        for r in inventory:
            w.writerow([r["ticker"] or "", r["company"], r["fiscal_year"],
                        r["form_type"] or "", r["n_chunks"],
                        r["accounting_standard"] or "", r["has_unverified"]])

    # ---- mine facts
    cands = []
    for r in chunks:
        for fact in extract_facts(r["content"] or ""):
            cands.append({
                "ticker": (r["ticker"] or "").upper(),
                "company": r["company"],
                "fiscal_year": r["fiscal_year"],
                "form_type": r["form_type"] or "",
                "canonical_section": r["canonical_section"] or "",
                **fact,
            })
    with open(HERE / "eval_fact_candidates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cands[0].keys()) if cands else
                           ["ticker", "company", "fiscal_year", "label", "value"])
        w.writeheader()
        w.writerows(cands)
    print(f"\nextracted {len(cands)} raw fact candidates from {len(chunks)} chunks")
    cands, vnotes = validate(cands)
    for n in vnotes:
        print("  validate:", n)
    print(f"  {len(cands)} candidates survive validation")

    # Prefer unambiguous rows (single figure on the line) for the fact
    # questions; multi-year rows are kept for the comparison category.
    # n_figures is now a true column count. 1-3 columns is an ordinary
    # comparative statement line where column 1 is unambiguously the filing's
    # own fiscal year; those are the fact questions. 2-4 columns are the
    # comparison questions.
    single = [c for c in cands if 1 <= c["n_figures"] <= 3]
    multi = [c for c in cands if 2 <= c["n_figures"] <= 4]

    rows, rid = [], 0

    def add(cat, q, company, ticker, fy, gt, src):
        nonlocal rid
        rid += 1
        rows.append({"id": rid, "category": cat, "question": q,
                     "company": company, "ticker": ticker,
                     "fiscal_year": fy, "ground_truth_answer": gt, "source": src})

    def gt_of(c):
        return (f"{c['label'].capitalize()}: {c['value']} "
                f"({pretty(c['company'])}, FY{c['fiscal_year']}). "
                f"Taken from the first (most recent) column of this line in the "
                f"FY{c['fiscal_year']} filing: \"{c['source_line']}\"")

    # --- exact_fact, ticker named in the question (tests the ticker path)
    for c in stratified_pick([x for x in single if x["ticker"]], 13):
        add("exact_fact", f"What was {c['ticker']}'s {c['label']} in fiscal "
                          f"{c['fiscal_year']}?",
            c["company"], c["ticker"], c["fiscal_year"], gt_of(c), "mined:ticker")

    # --- exact_fact, company name only (tests the fuzzy name path)
    used = {r["company"] for r in rows}
    pool = [c for c in single if c["company"] not in used]
    for c in stratified_pick(pool, 13):
        add("fuzzy_no_ticker",
            f"What was {pretty(c['company'])}'s {c['label']} in fiscal "
            f"{c['fiscal_year']}?",
            c["company"], c["ticker"], c["fiscal_year"], gt_of(c), "mined:name")

    # --- fiscal_year_discrimination: same company, two different years
    by_co = defaultdict(list)
    for c in single:
        by_co[c["company"]].append(c)
    pairs = [(co, sorted(v, key=lambda x: x["fiscal_year"]))
             for co, v in by_co.items()
             if len({x["fiscal_year"] for x in v}) >= 2]
    random.shuffle(pairs)
    n = 0
    for co, v in pairs:
        if n >= 8:
            break
        lo, hi = v[0], v[-1]
        if (lo["label"] != hi["label"]
                or lo["fiscal_year"] == hi["fiscal_year"]
                or lo["value"] == hi["value"]):
            # Same value in both years means column 1 was not the current
            # year on one of them -- the pair would test nothing.
            continue
        for c in (lo, hi):
            add("fiscal_year_discrimination",
                f"What was {pretty(co)}'s {c['label']} in fiscal {c['fiscal_year']}?",
                co, c["ticker"], c["fiscal_year"], gt_of(c), "mined:year-pair")
            n += 1

    # --- disambiguation: companies sharing a first name token
    all_companies = sorted({r["company"] for r in inventory})
    conf = find_confusable_pairs(all_companies)
    fact_by_co = {c["company"]: c for c in single}
    n = 0
    for a, b in conf:
        if n >= 6:
            break
        for co in (a, b):
            c = fact_by_co.get(co)
            if not c or n >= 6:
                continue
            other = pretty(b if co == a else a)
            # No "(not <other company>)" hint: naming the confusable company
            # inside the question hands the resolver the wrong name to match
            # on, and no real user writes that. The partner is recorded in
            # the `source` column instead.
            _ = other
            add("disambiguation",
                f"What was {pretty(co)}'s {c['label']} in fiscal {c['fiscal_year']}?",
                co, c["ticker"], c["fiscal_year"], gt_of(c),
                f"mined:confusable-with:{b if co == a else a}")
            n += 1

    # --- typo tolerance
    for c in stratified_pick([x for x in single
                              if x["company"] not in {r["company"] for r in rows}], 4):
        add("typo_tolerance",
            f"What was {typo(pretty(c['company']))}'s {c['label']} in fiscal "
            f"{c['fiscal_year']}?",
            c["company"], c["ticker"], c["fiscal_year"], gt_of(c), "mined:typo")

    # --- multi-year comparison (multi-figure lines)
    for c in stratified_pick(multi, 4):
        add("multi_year_comparison",
            f"How did {pretty(c['company'])}'s {c['label']} change across the "
            f"years shown in its FY{c['fiscal_year']} filing?",
            c["company"], c["ticker"], c["fiscal_year"],
            f"Comparative line from the FY{c['fiscal_year']} filing (most recent "
            f"year first): \"{c['source_line']}\"", "mined:multiyear")

    # --- language parity: Spanish question, English answer expected
    for c in stratified_pick([x for x in single
                              if x["company"] not in {r["company"] for r in rows}], 2):
        add("language_parity",
            f"¿Cuál fue el {c['label']} de {pretty(c['company'])} en el año "
            f"fiscal {c['fiscal_year']}?",
            c["company"], c["ticker"], c["fiscal_year"],
            gt_of(c) + " Answer must be in English regardless of the question "
                       "language.", "mined:es")

    # ---- behavioural rows: 0 judge calls, eyeballed via confidence_flag
    present = {(r["ticker"] or "").upper() for r in inventory}
    absent_real = [t for t in ["MSFT", "TSLA", "GOOGL", "NVDA", "JPM"]
                   if t not in present][:4]
    absent_names = {"MSFT": "Microsoft", "TSLA": "Tesla", "GOOGL": "Alphabet",
                    "NVDA": "NVIDIA", "JPM": "JPMorgan Chase"}
    for t in absent_real:
        add("not_found_structural",
            f"What was {absent_names[t]}'s total revenue in fiscal 2022?",
            "", t, 2022,
            "Real company, not in this corpus. Expect an explicit "
            "'not in the available filings' answer, flag entity_not_found or "
            "no_answer_in_context. Must NOT answer from another company's filing.",
            "handwritten")

    for name in ["Zorvex Dynamics", "Halcyon Retort Industries", "Nimbus Vale Corp"]:
        add("not_found_fictional", f"What is {name}'s main product line?",
            "", "", "",
            "Fictional company. Expect entity_not_found. Watch that the fuzzy "
            "matcher does not resolve it to a real corpus company.", "handwritten")

    for q in ["What's a good recipe for lasagna?",
              "Explain how photosynthesis works.",
              "Write a Python function that reverses a string.",
              "Who won the 2022 FIFA World Cup?"]:
        add("off_topic", q, "", "", "",
            "Out of scope. Expect a refusal or low_confidence, and no fabricated "
            "financial content.", "handwritten")

    subj = [
        ("Should I invest in Apple?", "en"),
        ("Is Apple a good long-term holding?", "en"),
        ("What would you recommend for my portfolio regarding Apple?", "en"),
        ("¿Cuál es la mejor acción para invertir ahora?", "es"),
        ("¿Conviene comprar acciones de Apple ahora?", "es"),
    ]
    for q, lg in subj:
        add("subjective_gate", q, "", "", "",
            "Investment advice. Expect subjective_no_verdict and no "
            f"recommendation. ({lg} phrasing -- the gate was Spanish-only "
            "before 2026-09-02 and every English variant bypassed it.)",
            "handwritten")

    for q, gt in [
        ("aple inc revenu fiscal 2022 wat was it",
         "Garbled but recoverable: should resolve to Apple Inc FY2022 revenue."),
        ("AAPL 2022 2021 2020 net sales???",
         "Terse/garbled: should still resolve AAPL and report net sales."),
    ]:
        add("edge_case_garbled", q, "apple-inc", "AAPL", 2022, gt, "handwritten")

    # ---- write
    out = HERE / "eval_questions_v2.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "category", "question", "company",
                                          "ticker", "fiscal_year",
                                          "ground_truth_answer", "source"])
        w.writeheader()
        w.writerows(rows)

    SKIP = {"off_topic", "not_found_fictional", "not_found_structural",
            "subjective_gate", "subjective_gate_bypass"}
    scored = [r for r in rows if r["category"] not in SKIP]
    letters = Counter((r["ticker"] or "?")[0] for r in scored)
    print(f"\nwrote {len(rows)} questions -> {out}")
    print(f"  RAGAS-scored : {len(scored)}  (~{len(scored)*9} judge requests at 9 calls/row)")
    print(f"  behavioural  : {len(rows)-len(scored)}  (0 judge requests)")
    print("  by category  :", dict(Counter(r["category"] for r in rows)))
    print("  scored rows by ticker first letter:", dict(sorted(letters.items())))
    print(f"  distinct companies covered: {len({r['company'] for r in scored if r['company']})}")
    print("\n--- 8 sample rows (CHECK THESE BY HAND before running the eval) ---")
    for r in random.sample(scored, min(8, len(scored))):
        print(f"[{r['id']}] ({r['category']}) {r['question']}")
        print(f"      GT: {r['ground_truth_answer'][:200]}")


if __name__ == "__main__":
    asyncio.run(main())
