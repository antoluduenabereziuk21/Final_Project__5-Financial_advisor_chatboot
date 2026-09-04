"""Test-retest reliability of the RAGAS judge.

Two independent scoring passes over the IDENTICAL 50 rows — same questions,
same answers, same retrieved contexts, same reference. Nothing about the
system under test changed between them. Every difference is judge noise.

That matters because section 6 of the assessment reports point estimates. If
re-judging the same rows moves context_precision by 0.05, then a 0.05
improvement from a retrieval change means nothing, and any claim built on one
needs a wider margin than that.

    rag/.venv/Scripts/python.exe RAGAS/compare_judge_runs.py
    rag/.venv/Scripts/python.exe RAGAS/compare_judge_runs.py --b run3

Reports, per metric:
  mean A, mean B, and the shift between runs
  MAD          mean absolute per-row difference — the practical error bar
  max diff     worst single-row disagreement
  r            Pearson correlation of per-row scores across runs
  flip rate    for the near-binary metrics, share of rows that changed side
"""
import argparse
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def load(tag: str) -> pd.DataFrame:
    name = f"ragas_scores{'_' + tag if tag else ''}.csv"
    path = RESULTS / name
    if not path.exists():
        raise SystemExit(f"missing {path} -- run it with RAGAS_RUN_TAG={tag or '(none)'}")
    df = pd.read_csv(path, dtype={"id": str})
    return df.set_index("id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="", help="tag of the first run (default: none)")
    ap.add_argument("--b", default="run2", help="tag of the second run")
    args = ap.parse_args()

    A, B = load(args.a), load(args.b)
    metrics = [c for c in A.columns
               if c.startswith(("llm_", "context_", "answer_", "faith"))
               and c in B.columns]
    common = A.index.intersection(B.index)
    print(f"run A: {len(A)} rows | run B: {len(B)} rows | compared on {len(common)} shared rows\n")
    A, B = A.loc[common], B.loc[common]

    hdr = f"{'metric':<38}{'A':>7}{'B':>8}{'shift':>8}{'MAD':>7}{'max':>7}{'r':>7}{'flip':>7}"
    print(hdr)
    print("-" * len(hdr))
    for m in metrics:
        a, b = pd.to_numeric(A[m], errors="coerce"), pd.to_numeric(B[m], errors="coerce")
        ok = a.notna() & b.notna()
        a, b = a[ok], b[ok]
        d = (a - b).abs()
        r = a.corr(b)
        # "flip" = crossed the midpoint, i.e. the row changed side on a
        # metric that behaves close to binary (context_recall does).
        flip = ((a > 0.5) != (b > 0.5)).mean()
        print(f"{m:<38}{a.mean():>7.3f}{b.mean():>8.3f}{b.mean()-a.mean():>+8.3f}"
              f"{d.mean():>7.3f}{d.max():>7.3f}{(r if pd.notna(r) else float('nan')):>7.3f}"
              f"{flip:>7.1%}")

    print("\nRows where the two runs disagree most:")
    dif = pd.DataFrame({m: (pd.to_numeric(A[m], errors="coerce")
                            - pd.to_numeric(B[m], errors="coerce")).abs()
                        for m in metrics})
    worst = dif.sum(axis=1).sort_values(ascending=False).head(8)
    for rid, tot in worst.items():
        parts = ", ".join(f"{m.split('_')[-1]}: {A.loc[rid, m]:.2f}->{B.loc[rid, m]:.2f}"
                          for m in metrics
                          if abs(pd.to_numeric(pd.Series([A.loc[rid, m]]), errors='coerce')[0]
                                 - pd.to_numeric(pd.Series([B.loc[rid, m]]), errors='coerce')[0]) > 0.01)
        print(f"  id {rid:>3}  total drift {tot:.2f}  ({parts})")

    print("\nHow to read this: MAD is the error bar. A change to the system that "
          "moves a metric by less than MAD has not been shown to do anything.")


if __name__ == "__main__":
    main()
