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

# SEC-standardized cover-page language, confirmed present immediately after
# the real registrant name on both a 10-K (ACADIA: "ACADIA PHARMACEUTICALS
# INC.\n(Exact Name of Registrant as Specified in Its Charter)") and a 20-F
# (36Kr Holdings Inc., same phrase). \s* tolerance for the same zero-space
# extraction defect handled elsewhere in this module.
REGISTRANT_NAME_RE = re.compile(
    r"([^\n]{3,120})\n\(Exact\s*Name\s*of\s*Registrant\s*as\s*Specified\s*in\s*[Ii]ts\s*Charter\)",
    re.IGNORECASE,
)

CORP_SUFFIX_RE = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|llc|lp|l\.p|plc|holdings|group|the)\b\.?",
    re.IGNORECASE,
)

# "formerly known as X" / "formerly named X" -- a legitimate corporate
# rename, not a corpus defect. SEC cover pages report the CURRENT legal
# name; the former name (which is what the source folder is usually named
# after, since folders were derived from an earlier ticker/name snapshot)
# often only appears later, e.g. in Item 1 Business. Confirmed real case:
# Eldorado-Resorts-Inc/NASDAQ_ERI_2020.pdf's cover page correctly says
# "CAESARS ENTERTAINMENT, INC." -- the phrase "a Delaware corporation
# formerly known as Eldorado Resorts, Inc." only appears in Item 1,
# several hundred characters later.
RENAME_RE = re.compile(r"formerly\s+(?:known\s+as|named)\s+([^.,\n]{3,80})", re.IGNORECASE)

# Common English function words -- if 2+ show up in a "registrant name"
# capture, it's a business-description sentence, not a name. Confirmed
# real case: Green-Plains-Partners-LP/NASDAQ_GPP_2021.pdf's cover page
# has a two-column layout (a sidebar description running alongside the
# title stack); pdfplumber's line ordering interleaves them, so the line
# immediately before "(Exact Name of Registrant...)" is "ethanol and fuel
# storage, terminals, transportation assets and other" instead of the
# actual name "GREEN PLAINS PARTNERS LP", which sits two lines above it.
_PROSE_STOPWORDS = {"and", "the", "of", "to", "by", "or", "in", "for", "from", "as", "other", "a", "an", "with"}

# Confirmed real case: biotelemetry-inc/NASDAQ_BEAT_2017.pdf -- the
# registrant name is genuinely absent from pdfplumber's raw text
# extraction on the cover page (not a cleaning.py stripping bug; checked
# the untouched raw page text directly and the name was never there,
# likely a corrupted/missing font on that specific PDF -- consistent with
# the "FontBBox" pdfminer warnings cleaning.py already suppresses). When
# the name line is missing, REGISTRANT_NAME_RE's capture group falls
# through to whatever IS on the line before the marker, which is reliably
# "Commission file number: ..." on SEC cover pages. No text-extraction
# strategy recovers text that was never there -- reject this pattern
# outright so it reports "couldn't check" instead of a wrong name.
_NOT_A_NAME_RE = re.compile(r"^commission\s+file\s+number", re.IGNORECASE)


def _looks_like_company_name(name: str) -> bool:
    if _NOT_A_NAME_RE.match(name.strip()):
        return False
    """Rejects two confirmed failure modes of REGISTRANT_NAME_RE's capture:
    (1) severe character-level extraction corruption -- confirmed real case:
    activision-blizzard-inc/NASDAQ_ATVI_2019.pdf's cover page renders the
    "(Exact Name...)" boilerplate TWICE, once as a decorative overlay whose
    characters interleave with spaces ("EE Exx xaa acc ctt t..."), which
    pdfplumber reads as one long run of near-random 1-3 char fragments.
    Real names, even short ones, don't produce >=10 tokens averaging under
    3.5 chars each -- that combination only shows up on corrupted text in
    every sample checked. (2) a business-description sentence captured
    instead of a name (see _PROSE_STOPWORDS above)."""
    tokens = name.split()
    if not tokens:
        return False
    if len(tokens) >= 10 and (sum(len(t) for t in tokens) / len(tokens)) < 3.5:
        return False
    stopword_hits = sum(1 for t in tokens if t.lower().strip(",.") in _PROSE_STOPWORDS)
    if stopword_hits >= 2:
        return False
    return True


def _collapsed(name: str) -> str:
    """All whitespace/punctuation stripped, lowercased -- catches a spurious
    mid-word space without losing the word the way token-set comparison
    does. Confirmed real case: T2-biosystems/NASDAQ_TTOO_2016.pdf extracts
    as "T2 Biosys tems, Inc." (a kerning/spacing artifact in the source
    PDF, not a corruption of the underlying text) -- token-set overlap
    fails because "biosystems" was split into "biosys" and "tems", neither
    of which matches "biosystems" from the folder name. Comparing fully
    collapsed strings ("t2biosystems" vs "t2biosystemsinc") finds the match
    regardless of where the extra space landed."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _significant_tokens(name: str) -> set:
    """Lowercased, corporate-suffix-stripped, punctuation-stripped word
    tokens of length >= 3 -- used to compare a name found two different
    ways (filename-derived vs cover-page text) without being thrown off by
    "Inc." vs "Incorporated", hyphens vs spaces, etc."""
    if not name:
        return set()
    name = CORP_SUFFIX_RE.sub(" ", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    return {tok for tok in name.split() if len(tok) >= 3}


def company_from_path(pdf_path: str) -> str:
    # folder name one level up from the file, e.g. .../21vianet-group-inc/NASDAQ_VNET_2019.pdf
    return os.path.basename(os.path.dirname(pdf_path))


def detect_registrant_name(cover_text: str):
    m = REGISTRANT_NAME_RE.search(cover_text or "")
    if not m:
        return None
    candidate = m.group(1).strip()
    if not _looks_like_company_name(candidate):
        return None  # garbled extraction or a prose line, not a real name -- see _looks_like_company_name
    return candidate


def check_company_name_mismatch(folder_company: str, cover_text: str):
    """
    Cross-checks the folder-derived company name against the actual
    registrant name on the cover page -- built specifically because of the
    NASDAQ_DDD_2021.pdf finding (filed under 3d-systems-corp's folder, but
    is genuinely 36Kr Holdings Inc.'s Form 20-F). That mismatch was found
    by manual inspection, not an automated check -- this is that check.

    Returns (registrant_name, mismatch: bool | None). mismatch is None if
    the registrant name couldn't be found on the cover page at all (can't
    conclude either way -- do not default to False, which would silently
    read as "checked, no problem found").

    Comparison is token-overlap based, not exact string equality: folder
    names are hyphenated/abbreviated ("3d-systems-corp") and cover-page
    names are formal ("3D Systems Corporation") -- exact match would
    false-positive on every single document. Any shared significant token
    (>=3 chars, corporate suffixes like Inc/Corp/Holdings stripped from
    both sides) counts as a match; zero overlap is flagged as a mismatch.
    """
    registrant_name = detect_registrant_name(cover_text)
    if not registrant_name:
        return None, None

    folder_tokens = _significant_tokens(folder_company)
    registrant_tokens = _significant_tokens(registrant_name)
    if not folder_tokens or not registrant_tokens:
        return registrant_name, None

    if folder_tokens & registrant_tokens:
        return registrant_name, False

    # Secondary check 1: mid-word space artifact (see _collapsed).
    folder_collapsed = _collapsed(folder_company)
    registrant_collapsed = _collapsed(registrant_name)
    if folder_collapsed and registrant_collapsed and (
        folder_collapsed in registrant_collapsed or registrant_collapsed in folder_collapsed
    ):
        return registrant_name, False

    # Secondary check 2: legitimate rename, folder still uses the old name
    # (see RENAME_RE).
    for m in RENAME_RE.finditer(cover_text or ""):
        if _significant_tokens(m.group(1)) & folder_tokens:
            return registrant_name, False

    return registrant_name, True


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
    registrant_name, company_name_mismatch = check_company_name_mismatch(company, cover_text)

    return {
        "company": company,
        "registrant_name": registrant_name,  # from cover-page text -- see check_company_name_mismatch
        "company_name_mismatch": company_name_mismatch,  # True/False/None (None = couldn't check)
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
