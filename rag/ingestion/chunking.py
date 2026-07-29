"""
Stage 3 -- chunking, per SPEC.md section 5.

Two strategies, compared side by side rather than one assumed correct:
  1. word_count            -- Haystack DocumentSplitter, split_by="word",
                               split_length=350, split_overlap=50
  2. structure_then_word_count -- detect Item/Part boundaries first via
                               regex, then apply the same word-count
                               splitter within each detected section
"""
import re
import uuid

from haystack import Document
from haystack.components.preprocessors import DocumentSplitter

ITEM_RE = re.compile(r"^\s*ITEM\s*(\d+[A-Z]?(?:\.\d+)?(?:\.[A-Z])?)\.?[\s—-]", re.IGNORECASE | re.MULTILINE)
PART_RE = re.compile(r"^\s*PART\s*([IVX]+)\b", re.IGNORECASE | re.MULTILINE)
# \s* not \s+ on both -- confirmed on real data (ACADIA 2018 10-K table of
# contents: "Item1. Business", "PARTI") that the same zero-space extraction
# defect cleaning.py works around also glues these headers with no space
# after ITEM/PART. Note this runs on cleaning.py's *output*, which has
# already been through deglue_words() -- but that only fires on tokens
# >=15 chars, and "Item1" (5 chars) is under that threshold, so it survives
# unglued. Handling it here directly is more reliable than lowering the
# global threshold, which would start mangling other short real words.

_splitter = DocumentSplitter(split_by="word", split_length=350, split_overlap=50)
_splitter.warm_up()


def chunk_word_count(text: str, source_file: str):
    doc = Document(content=text)
    result = _splitter.run(documents=[doc])
    chunks = []
    for d in result["documents"]:
        chunks.append({
            "chunk_id": str(uuid.uuid4())[:8],
            "text": d.content,
            "word_count": len(d.content.split()),
            "source_file": source_file,
            "split_method": "word_count",
        })
    return chunks


def detect_structure_boundaries(text: str):
    """
    Returns a list of (start_char_offset, label) for each detected Item/Part
    boundary, sorted by position. label is e.g. "Item 1A" or "Part III".
    Empty list if nothing detected -- caller must fall back to word_count
    only, not assume structure exists.
    """
    boundaries = []
    for m in ITEM_RE.finditer(text):
        boundaries.append((m.start(), f"Item {m.group(1).upper()}"))
    for m in PART_RE.finditer(text):
        boundaries.append((m.start(), f"Part {m.group(1).upper()}"))
    boundaries.sort(key=lambda x: x[0])
    return boundaries


MIN_SECTION_WORDS = 30  # below this, treat as a table-of-contents line, not a real section


def chunk_structure_then_word_count(text: str, source_file: str):
    """
    Confirmed on real data (ACADIA 2018 10-K): a plain Item/Part regex also
    matches every line of the filing's own table of contents ("Item1.
    Business.......1"), inflating boundary count ~3x over the real ~15-20
    items a 10-K has and producing spurious few-word "sections". Filtering
    by minimum section length is a heuristic, not a proper TOC detector --
    flagged as worth revisiting (e.g. detecting dot-leader lines directly)
    rather than treated as fully solved.
    """
    raw_boundaries = detect_structure_boundaries(text)
    if not raw_boundaries:
        return [], {"boundaries_detected": 0, "boundaries_after_toc_filter": 0}

    # first pass: compute each boundary's section length to decide what to keep
    boundaries = []
    for i, (start, label) in enumerate(raw_boundaries):
        end = raw_boundaries[i + 1][0] if i + 1 < len(raw_boundaries) else len(text)
        if len(text[start:end].split()) >= MIN_SECTION_WORDS:
            boundaries.append((start, label))

    if not boundaries:
        return [], {"boundaries_detected": len(raw_boundaries), "boundaries_after_toc_filter": 0}

    sections = []
    for i, (start, label) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        section_text = text[start:end]
        if section_text.strip():
            sections.append((label, section_text))

    chunks = []
    for label, section_text in sections:
        doc = Document(content=section_text)
        result = _splitter.run(documents=[doc])
        for d in result["documents"]:
            chunks.append({
                "chunk_id": str(uuid.uuid4())[:8],
                "text": d.content,
                "word_count": len(d.content.split()),
                "source_file": source_file,
                "split_method": "structure_then_word_count",
                "detected_label": label,
            })
    return chunks, {"boundaries_detected": len(raw_boundaries), "boundaries_after_toc_filter": len(boundaries), "sections": len(sections)}


if __name__ == "__main__":
    sample = """PART I

Item 1. Business

We are a company that does things. """ + ("word " * 500) + """

Item 1A. Risk Factors

Things could go wrong. """ + ("risk " * 500) + """

PART II

Item 7. Management's Discussion and Analysis

Numbers went up. """ + ("analysis " * 500)

    wc = chunk_word_count(sample, "test.pdf")
    print(f"word_count strategy: {len(wc)} chunks")
    for c in wc[:3]:
        print(f"  {c['word_count']} words: {c['text'][:60]!r}...")

    sc, report = chunk_structure_then_word_count(sample, "test.pdf")
    print(f"\nstructure_then_word_count: {report}, {len(sc)} chunks")
    for c in sc[:5]:
        print(f"  [{c['detected_label']}] {c['word_count']} words: {c['text'][:60]!r}...")
