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
import logging
import re
import unicodedata

import pdfplumber
import wordninja

# pdfminer (which pdfplumber sits on top of) logs WARNING-level messages to
# stderr for cosmetic PDF-generation quirks it can't fully parse -- missing
# FontBBox on a font descriptor, a pattern-fill color reference (e.g. "/P1")
# where a plain gray float is expected, etc. These do not raise exceptions
# and do not drop any extracted text; pdfminer just skips that one detail
# and continues. Common on SEC filings with letterhead/logo graphics.
# Silenced here because at 300-file batch scale this noise buries the
# actual per-file "ok"/"FAILED" progress lines in run_batch.py's output.
logging.getLogger("pdfminer").setLevel(logging.ERROR)

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

# Dot-leader fill ("March 31, 2016 ...................... $ 7.64") -- SEC
# filings use this for both real label/value data rows and table-of-contents
# entries. Collapsing a long run down to a short fixed marker keeps the
# label/value association (nothing on either side of the run is touched)
# while removing the wasted space -- a single TOC-style line can otherwise
# burn 50+ characters of a chunk's word budget on literal periods.
DOT_RUN_RE = re.compile(r"\.(?:\s?\.){3,}")
DOT_RUN_REPLACEMENT = " ... "

# Table-of-contents detection: a TOC line is "<label> <dot leader> <ONE
# trailing number>" (the page number) -- exactly the same dot-leader
# convention real data rows use, distinguished only by having a single
# trailing value instead of 2+ (confirmed in pre_procesing_1: this is what
# separates "Item 1. Business.......1" from "March 31, 2016 ...... $7.64
# $5.32"). A page where several lines match that single-value pattern is a
# table of contents, not real content -- excluded from chunking entirely
# (see clean_from_raw_pages), since it duplicates section titles already
# captured via item/part structure detection and adds no informational
# value on its own.
TOC_LINE_RE = re.compile(r"^.+?" + DOT_RUN_RE.pattern + r"\s*\d+\s*$")
TOC_MIN_MATCHING_LINES = 3


def is_toc_page(text: str) -> bool:
    lines = (text or "").split("\n")
    hits = sum(1 for ln in lines if TOC_LINE_RE.match(ln.strip()))
    return hits >= TOC_MIN_MATCHING_LINES


def collapse_dot_leaders(text: str) -> str:
    return DOT_RUN_RE.sub(DOT_RUN_REPLACEMENT, text)


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

    Returns (full_text, cleaned_pages, page_offsets, report):
      full_text: str, built from BODY pages only (cover page and any
        table-of-contents pages excluded -- see is_toc_page above; they
        add no retrievable value and were wasting chunk budget).
      cleaned_pages: list of dicts {page_number, text, page_type} for
        EVERY page after the front-matter cutoff (cover/toc included, so
        callers needing e.g. cover-page text for metadata still have it --
        only full_text/chunking skips non-body pages).
      page_offsets: list of (start_char, end_char, page_number) for each
        body page's span within full_text -- lets a chunk's character
        range be mapped back to its REAL source page number(s) exactly,
        instead of the proportional-fraction estimate used previously.
      report: dict, same fields as before plus n_cover_pages_excluded /
        n_toc_pages_excluded.
    """
    pages_text = [text for _, text in raw_pages]
    page_numbers = [pn for pn, _ in raw_pages]

    cutoff_page, marker_found = find_front_matter_cutoff(pages_text)
    body_text = pages_text[cutoff_page:]
    body_page_numbers = page_numbers[cutoff_page:]

    boilerplate, repeat_report = find_repeated_boilerplate_lines(body_text)

    cleaned_pages = []
    page_offsets = []
    total_deglued = 0
    n_toc_excluded = 0
    running_offset = 0
    for i, (page_number, text) in enumerate(zip(body_page_numbers, body_text)):
        # Only the page find_front_matter_cutoff actually MATCHED on counts
        # as "cover" -- when marker_found is False, cutoff_page is just the
        # 0-fallback (see find_front_matter_cutoff), not a real detected
        # cover page, and treating body_text[0] as "the cover page" in that
        # case would wrongly exclude real content. Confirmed on PRTK_2015
        # (the 3-page non-10-K notice, no real cover marker at all): before
        # this check, its only substantive page was being discarded as a
        # false "cover page".
        page_is_cover = marker_found and (i == 0)

        # The cover page is exempted from boilerplate stripping. The
        # registrant name (e.g. "Blackbaud, Inc.") legitimately repeats as
        # a running header/footer on most BODY pages -- which is exactly
        # what makes find_repeated_boilerplate_lines correctly flag it as
        # boilerplate -- but stripping it from the COVER page too deletes
        # the one place it's load-bearing content, not noise. Confirmed
        # real case: blackbaud-inc/NASDAQ_BLKB_2018.pdf -- "Blackbaud,
        # Inc." was the only line detected as boilerplate, and stripping it
        # from the cover page silently deleted the registrant name, so
        # REGISTRANT_NAME_RE fell through to capturing the next line up
        # ("Commission file number: 000-50600") instead -- confirmed the
        # same mechanism on bloomin-brands-inc ("BLOOMIN' BRANDS, INC.").
        # TOC check runs on boilerplate-stripped but otherwise raw text --
        # dot-leader lines need to still be intact to detect, so this must
        # happen before collapse_dot_leaders.
        if not page_is_cover:
            text = strip_boilerplate(text, boilerplate)
        page_is_toc = is_toc_page(text)

        text = clean_unicode(text)
        text = dehyphenate(text)
        text, n_fixed = deglue_words(text)
        total_deglued += n_fixed
        text = collapse_dot_leaders(text)
        text = normalize_whitespace(text)

        page_type = "cover" if page_is_cover else ("toc" if page_is_toc else "body")
        if page_type == "toc":
            n_toc_excluded += 1
        cleaned_pages.append({"page_number": page_number, "text": text, "page_type": page_type})

        if page_type == "body":
            start = running_offset
            # matches how full_text is joined below: "\n\n" between pages
            end = start + len(text)
            page_offsets.append((start, end, page_number))
            running_offset = end + 2  # +2 for the "\n\n" joiner

    full_text = "\n\n".join(p["text"] for p in cleaned_pages if p["page_type"] == "body")
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
        "n_cover_pages_excluded": sum(1 for p in cleaned_pages if p["page_type"] == "cover"),
        "n_toc_pages_excluded": n_toc_excluded,
        "word_count": word_count,
        "flagged_low_word_count": word_count < 500,
    }
    return full_text, cleaned_pages, page_offsets, report


def page_number_for_offset(page_offsets: list, char_offset: int):
    """Exact page lookup for a character offset into full_text (see
    clean_from_raw_pages), replacing the old proportional-fraction
    estimate. Returns None if out of range (shouldn't happen for offsets
    actually taken from full_text, but callers should not assume)."""
    for start, end, page_number in page_offsets:
        if start <= char_offset < end:
            return page_number
    if page_offsets and char_offset >= page_offsets[-1][1]:
        return page_offsets[-1][2]  # end-of-document edge case
    return None


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
    full_text, pages, page_offsets, report = clean_document(path)
    print(report)
    print("---first 500 chars of cleaned body---")
    print(full_text[:500])
