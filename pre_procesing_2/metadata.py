"""
Stage metadata, per SPEC.md section 6.
"""
import os
import re

from canonical_sections import canonical_section_for

TICKER_RE = re.compile(r"NASDAQ_([A-Z]+)_(\d{4})", re.IGNORECASE)

FORM_TYPE_RE = re.compile(
    r"FORM\s+(10-K|20-F).{0,400}?REPORT\s+PURSUANT\s+TO\s+SECTION\s+13\s+OR\s+15\(d\)",
    re.IGNORECASE | re.DOTALL,
)
# Fallback for a second, nastier real defect: some source PDFs extract with
# *zero* spaces between words at all (confirmed on ACADIA's 2018 10-K --
# "ANNUALREPORTPURSUANTTOSECTION13OR15(d)..."), a font/kerning artifact where
# pdfplumber has no positional gap to infer a space from. \s+ can never match
# that; \s* (zero-or-more) does, at the cost of being marginally more
# permissive. Tried only when the strict pattern fails.
FORM_TYPE_RE_NOSPACE = re.compile(
    r"FORM\s*(10-K|20-F).{0,400}?REPORT\s*PURSUANT\s*TO\s*SECTION\s*13\s*OR\s*15\(d\)",
    re.IGNORECASE | re.DOTALL,
)

FISCAL_YEAR_RE = re.compile(
    r"(?:fiscal\s+year\s+ended|for\s+the\s+year\s+ended)\D{0,10}"
    r"(?:\w+\s+\d{1,2},?\s+)?(\d{4})",
    re.IGNORECASE,
)

# Form 20-F cover-page accounting-basis checkbox -- confirmed language:
# "indicate by check mark which basis of accounting the registrant has used
# to prepare the financial statements"
ACCOUNTING_BASIS_BLOCK_RE = re.compile(
    r"basis of accounting.{0,600}",
    re.IGNORECASE | re.DOTALL,
)


def company_from_path(pdf_path: str) -> str:
    # folder name one level up from the file, e.g. .../21vianet-group-inc/NASDAQ_VNET_2019.pdf
    return os.path.basename(os.path.dirname(pdf_path))


def ticker_and_filename_year(pdf_path: str):
    m = TICKER_RE.search(os.path.basename(pdf_path))
    if not m:
        return None, None
    return m.group(1).upper(), int(m.group(2))


def detect_form_type(cover_text: str):
    """Same anchor phrase as cleaning.FRONT_MATTER_RE, kept independent on
    purpose -- metadata extraction should not silently depend on cleaning
    having run first, and testing them separately catches drift."""
    text = cover_text or ""
    m = FORM_TYPE_RE.search(text) or FORM_TYPE_RE_NOSPACE.search(text)
    if not m:
        return None
    return m.group(1).upper()


def detect_fiscal_year(cover_text: str):
    m = FISCAL_YEAR_RE.search(cover_text or "")
    if not m:
        return None
    return int(m.group(1))


def detect_accounting_standard(form_type: str, cover_text: str):
    """
    10-K: deterministic, no detection needed -- domestic filers must use US GAAP.
    20-F: locate the cover-page checkbox block and determine which option is
    marked (x / ☒ vs blank / ☐ / o). Returns None if the block isn't found
    or no option is clearly marked -- do not guess.
    """
    if form_type == "10-K":
        return "US GAAP"
    if form_type != "20-F":
        return None

    m = ACCOUNTING_BASIS_BLOCK_RE.search(cover_text or "")
    if not m:
        return None
    block = m.group(0)

    # look for a mark (x, X, ☒) immediately preceding each option's label
    checks = {
        "US GAAP": re.search(r"[xX☒]\s*U\.?S\.?\s*GAAP", block),
        "IFRS": re.search(r"[xX☒]\s*International\s+Financial\s+Reporting\s+Standards", block),
        "Other": re.search(r"[xX☒]\s*Other", block),
    }
    marked = [k for k, v in checks.items() if v]
    if len(marked) == 1:
        return marked[0]
    return None  # zero or multiple marks found -- ambiguous, don't guess


NUMERIC_DENSITY_THRESHOLD = 0.10  # see SPEC.md section 6 -- calibrated on real
# chunk output from 4 sample docs (PIH_2016, ACAD_2018, GPP_2019, PRTK_2015):
# each shows a low-density majority with a distinct high-density tail: median
# density 0.01-0.08, tail up to 0.27-0.40. 0.10 sits inside that tail cleanly
# across all 4 without being so low it catches ordinary narrative.


def _is_numeric_ish(token: str, ratio_threshold: float = 0.6) -> bool:
    """A token counts as numeric if, after stripping currency/percent/paren/
    comma/dot/space decoration, what's left is digit-dominant. Same test
    used in pre_procesing_1/table_extraction.py to separate real table
    cells from prose, re-applied per-word here instead of per-cell."""
    core = re.sub(r"[\$,%()\-.\s]", "", str(token))
    if not core:
        return False
    digits = sum(ch.isdigit() for ch in core)
    return (digits / len(core)) >= ratio_threshold


def numeric_density(chunk_text: str):
    """Returns (density, likely_numeric_dense) for a chunk of text. Not a
    table detector -- also flags numeric-heavy narrative (MD&A prose full of
    dollar figures) and structured non-table content (exhibit indices,
    legal reference lists), confirmed by inspecting chunks at the threshold
    boundary. Deliberate: with no table index in this pipeline (SPEC.md
    section 9), the goal is surfacing chunks likely to answer a number-
    seeking query, not classifying "is this literally a table"."""
    tokens = chunk_text.split()
    if not tokens:
        return 0.0, False
    numeric = sum(1 for t in tokens if _is_numeric_ish(t))
    density = numeric / len(tokens)
    return density, density >= NUMERIC_DENSITY_THRESHOLD


def build_metadata(pdf_path: str, cover_text: str, item_number: str = None):
    company = company_from_path(pdf_path)
    ticker, filename_year = ticker_and_filename_year(pdf_path)
    form_type = detect_form_type(cover_text)
    fiscal_year = detect_fiscal_year(cover_text) or filename_year
    accounting_standard = detect_accounting_standard(form_type, cover_text)
    canonical_section = canonical_section_for(form_type, item_number, cover_text) if form_type and item_number else None

    return {
        "company": company,
        "ticker": ticker,
        "form_type": form_type,
        "fiscal_year": fiscal_year,
        "fiscal_year_from_filename": filename_year,
        "fiscal_year_matches_filename": (detect_fiscal_year(cover_text) == filename_year) if detect_fiscal_year(cover_text) else None,
        "item_number": item_number,
        "canonical_section": canonical_section,
        "accounting_standard": accounting_standard,
    }


if __name__ == "__main__":
    import sys
    import pdfplumber

    path = sys.argv[1]
    with pdfplumber.open(path) as pdf:
        cover_text = "\n".join((p.extract_text() or "") for p in pdf.pages[:5])
    meta = build_metadata(path, cover_text)
    for k, v in meta.items():
        print(f"  {k}: {v}")
