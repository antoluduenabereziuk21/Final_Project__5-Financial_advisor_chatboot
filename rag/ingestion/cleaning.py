"""
Stage 2 -- cleaning, per SPEC.md section 4.

v2 change (see SPEC.md section 9): no table bounding-box exclusion. Table
regions are no longer detected or removed -- whatever pdfplumber's
page.extract_text() returns is what gets cleaned, tables included.

Page-range batching added here for the same reason table_extraction.py had
it in pre_procesing_1: measured directly on NASDAQ_AMRK_2021.pdf,
page.extract_text() alone costs ~0.57s/page on this specific file
(unrelated to tables -- confirmed by profiling with no bbox logic involved
at all), so a 121-page file alone exceeds this environment's 45s/call
budget before any cleaning even runs, and the two largest samples
(289/483 pages) would be far worse. Front-matter detection and boilerplate-
repeat-rate detection both need the FULL document's page list at once, so
only the raw-text-extraction step can be batched/cached across calls --
extract_raw_pages() does that; clean_from_raw_pages() runs the rest once
all pages are assembled. clean_document() is a single-call convenience
wrapper for documents short enough not to need batching.
"""
import re
import unicodedata

import pdfplumber
import wordninja

# Confirmed real defect: some source PDFs (e.g. ACADIA's 2018 10-K) extract
# with no space characters between words at all across large sections --
# "ANNUALREPORTPURSUANTTOSECTION13...". This isn't cosmetic: word-count-based
# operations downstream (this module's own word_count field, and Haystack's
# split_by="word" chunker) both tokenize on whitespace, so glued text is
# silently undercounted and produces far fewer, far larger real chunks than
# intended -- confirmed on this file: a 106-page document produced 3 chunks
# instead of the ~150+ expected. GLUED_TOKEN_RE below flags any token this
# long as a candidate for wordninja segmentation; anything shorter is left
# alone (real long words/identifiers exist and don't need this).
GLUED_TOKEN_RE = re.compile(r"\b\w{15,}\b")

FRONT_MATTER_RE = re.compile(
    r"UNITED\s+STATES\s+SECURITIES\s+AND\s+EXCHANGE\s+COMMISSION.{0,400}?FORM\s+(10-K|20-F)"
    r".{0,400}?REPORT\s+PURSUANT\s+TO\s+SECTION\s+13\s+OR\s+15\(d\)",
    re.IGNORECASE | re.DOTALL,
)
# Fallback for PDFs that extract with zero spaces between words (see
# metadata.FORM_TYPE_RE_NOSPACE for the confirmed real example -- ACADIA's
# 2018 10-K). Tried only when the strict pattern fails.
FRONT_MATTER_RE_NOSPACE = re.compile(
    r"UNITED\s*STATES\s*SECURITIES\s*AND\s*EXCHANGE\s*COMMISSION.{0,400}?FORM\s*(10-K|20-F)"
    r".{0,400}?REPORT\s*PURSUANT\s*TO\s*SECTION\s*13\s*OR\s*15\(d\)",
    re.IGNORECASE | re.DOTALL,
)
# Deliberately requires BOTH the form declaration AND the "REPORT PURSUANT TO
# SECTION 13 OR 15(d)" phrase together (not "ANNUAL REPORT..." specifically --
# confirmed on real data that pdfplumber sometimes splits "ANNUAL" around an
# adjacent checkbox glyph, breaking an exact-word match; "REPORT PURSUANT..."
# alone still distinguishes a real cover page from other SEC forms). A looser
# regex (form declaration alone) false-positives on other SEC forms that
# merely list "Form 10-K" as one checkbox among several -- confirmed on real
# data: Form 12b-25 (Notification of Late Filing) does exactly this and is
# not an annual report at all. Real production data will contain this kind
# of document-type contamination; catching it here matters, not just here.

DEHYPHENATE_RE = re.compile(r"([a-z])-\n([a-z])")
WHITESPACE_RE = re.compile(r"[ \t]+")
MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def extract_raw_pages(pdf_path: str, page_start: int = 1, page_end: int = None):
    """
    Plain page.extract_text() per page, no table logic at all. Returns a
    list of (page_number, text) tuples for [page_start, page_end] inclusive
    (1-indexed) so batches from separate calls can be merged and sorted by
    page_number before being handed to clean_from_raw_pages.
    """
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        end = page_end or len(pdf.pages)
        for page_number, page in enumerate(pdf.pages, start=1):
            if page_number < page_start or page_number > end:
                continue
            pages.append((page_number, page.extract_text() or ""))
    return pages


def find_front_matter_cutoff(pages_text: list):
    """
    Returns the 0-indexed page number where the real filing starts (per the
    SEC-standardized cover-page marker), or 0 if the marker is never found
    -- explicitly logged as a miss, not silently treated as "no front matter".
    """
    for i, text in enumerate(pages_text):
        t = text or ""
        if FRONT_MATTER_RE.search(t) or FRONT_MATTER_RE_NOSPACE.search(t):
            return i, True
    return 0, False  # marker not found -- caller must log this, not assume clean


def deglue_words(text: str):
    """
    Segments anomalously long whitespace-free tokens back into real words
    via wordninja (dictionary/frequency-based, not layout-based -- this is
    a last resort for text where the PDF itself lost the space information,
    not a substitute for fixing extraction). Returns (fixed_text, n_tokens_fixed).
    """
    n_fixed = 0

    def _replace(m):
        nonlocal n_fixed
        n_fixed += 1
        return " ".join(wordninja.split(m.group(0)))

    fixed = GLUED_TOKEN_RE.sub(_replace, text)
    return fixed, n_fixed


def dehyphenate(text: str) -> str:
    return DEHYPHENATE_RE.sub(r"\1\2", text)


def normalize_whitespace(text: str) -> str:
    text = WHITESPACE_RE.sub(" ", text)
    text = MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


def clean_unicode(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch.isprintable())


def find_repeated_boilerplate_lines(pages_text: list, threshold: float = 0.6):
    """
    A line repeating near-identically across >= threshold fraction of pages
    is treated as boilerplate. Returns (set of boilerplate lines, repeat-rate
    report) -- the report is what SPEC.md asks to inspect before trusting
    the threshold, not just the stripped output.
    """
    from collections import Counter
    n_pages = len(pages_text)
    counts = Counter()
    for text in pages_text:
        lines = {ln.strip() for ln in (text or "").split("\n") if ln.strip()}
        counts.update(lines)
    boilerplate = {line for line, c in counts.items() if n_pages > 0 and c / n_pages >= threshold}
    report = sorted(((line, c / n_pages) for line, c in counts.items() if c / n_pages >= 0.3),
                     key=lambda x: -x[1])
    return boilerplate, report


def strip_boilerplate(text: str, boilerplate: set) -> str:
    lines = text.split("\n")
    kept = [ln for ln in lines if ln.strip() not in boilerplate]
    return "\n".join(kept)


def clean_from_raw_pages(raw_pages: list, pdf_path: str):
    """
    Shared Stage 2 logic, taking already-extracted (page_number, text)
    tuples rather than a pdf_path -- this is what lets large documents be
    batched: extract_raw_pages() can be called across multiple short-lived
    calls (with results cached to disk and merged, same pattern as
    pre_procesing_1's table_extraction tables_cache), and this function
    only runs once over the complete, merged page list. front-matter
    detection and boilerplate repeat-rate detection both need every page at
    once -- there is no way to batch those two steps themselves.

    raw_pages must be sorted by page_number and cover the whole document
    (1..N with no gaps) -- caller's responsibility when merging batches.

    Returns (full_text, cleaned_pages, report) -- same shape as
    clean_document().
    """
    pages_text = [text for _, text in raw_pages]

    cutoff_page, marker_found = find_front_matter_cutoff(pages_text)
    body_pages = pages_text[cutoff_page:]

    boilerplate, repeat_report = find_repeated_boilerplate_lines(body_pages)

    cleaned_pages = []
    total_deglued = 0
    for text in body_pages:
        text = strip_boilerplate(text, boilerplate)
        text = clean_unicode(text)
        text = dehyphenate(text)
        text, n_fixed = deglue_words(text)
        total_deglued += n_fixed
        text = normalize_whitespace(text)
        cleaned_pages.append(text)

    full_text = "\n\n".join(cleaned_pages)
    word_count = len(full_text.split())

    report = {
        "source_file": pdf_path,
        "total_pages": len(pages_text),
        "front_matter_cutoff_page": cutoff_page,
        "front_matter_marker_found": marker_found,
        "boilerplate_lines_removed": len(boilerplate),
        "boilerplate_sample": [line for line, _ in repeat_report[:5]],
        "glued_tokens_deglued": total_deglued,
        "flagged_glued_text": total_deglued > 20,  # heuristic: this many hits means the doc has the defect broadly, not just an isolated identifier
        "word_count": word_count,
        "flagged_low_word_count": word_count < 500,
    }
    return full_text, cleaned_pages, report


def clean_document(pdf_path: str):
    """
    Single-call convenience wrapper for documents short enough not to need
    page-range batching (see module docstring). Large documents should call
    extract_raw_pages() in batches instead and pass the merged result to
    clean_from_raw_pages() directly -- orchestrate.py does this.
    """
    raw_pages = extract_raw_pages(pdf_path)
    return clean_from_raw_pages(raw_pages, pdf_path)


if __name__ == "__main__":
    import sys

    path = sys.argv[1]
    full_text, pages, report = clean_document(path)
    print(report)
    print("---first 500 chars of cleaned body---")
    print(full_text[:500])
