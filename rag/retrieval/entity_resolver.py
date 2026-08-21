from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

# Per-token similarity floor (SequenceMatcher.ratio(), 0-1) for a fuzzy
# company-name match to be trusted -- see _core_match_score. Uncalibrated --
# picked conservatively so an unconfident match fails open (no filter)
# rather than scoping retrieval to the wrong company. Revisit once there's a
# labeled question set (same open item as generator.py's 0.4 low_confidence
# threshold).
_COMPANY_MATCH_THRESHOLD = 0.8

_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

# Trailing legal-entity tokens stripped off a company slug before matching.
# Real questions name the company, not its corporate form -- "American
# Airlines", not "American Airlines Group Inc" -- and comparing a 2-token
# mention against a 4-token slug via a same-length sliding window scores far
# below threshold even for an exact-name match, because the window either
# grabs unrelated sentence words or misses tokens entirely. Confirmed
# empirically: "american-airlines-group-inc" only matched "How does American
# Airlines depreciate its aircraft?" after this stripping was added.
_CORP_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company",
    "group", "holdings", "holding", "ltd", "limited", "plc", "llc", "lp",
    "sa", "nv", "ag", "as",
}


def _normalize(text: str) -> str:
    """DB company values are slugs ("antares-pharma-inc"); questions are
    natural language ("Antares Pharma"). Normalize both to lowercase,
    space-separated tokens so they're comparable at all."""
    return re.sub(r"[-_./,]+", " ", text.lower()).strip()


def _core_tokens(tokens: list[str]) -> list[str]:
    """Strip trailing legal-entity suffix tokens ("inc", "group", ...) so
    matching targets the name a person would actually type. Only strips from
    the end, and never past the point of emptying the list entirely -- a
    slug that's nothing but suffix words falls back to itself unstripped."""
    trimmed = list(tokens)
    while len(trimmed) > 1 and trimmed[-1] in _CORP_SUFFIXES:
        trimmed.pop()
    return trimmed or tokens


def _core_match_score(question_tokens: list[str], core_tokens: list[str]) -> float:
    """For every core token (the company's name with legal-suffix words
    stripped), find its best per-token match anywhere in the question, then
    return the WEAKEST of those per-token scores -- every distinguishing
    word in the company name has to show up, not just one of them.

    This replaced an earlier whole-string sliding-window comparison
    (SequenceMatcher over concatenated windows) that was rejected after
    testing surfaced a real false positive: "What are general trends in the
    pharma industry?" scored 0.75 against "antares pharma" (threshold was
    0.72), because the *filler* word "the" happened to share enough
    characters with "antares" once concatenated with an exact match on
    "pharma" to clear the bar -- a generic industry question would have been
    wrongly scoped to one specific company. Per-token minimum scoring
    doesn't have this failure mode: "antares" has no good match anywhere in
    that sentence (best ratio ~0.4), so the weakest-token score stays low
    regardless of "pharma" matching perfectly.
    """
    if not core_tokens or not question_tokens:
        return 0.0
    per_token_best = []
    for token in core_tokens:
        best = max(
            (SequenceMatcher(None, token, qt).ratio() for qt in question_tokens),
            default=0.0,
        )
        per_token_best.append(best)
    return min(per_token_best)


@dataclass(frozen=True)
class KnownEntity:
    """One company actually present in the loaded corpus. Sourced from
    `documents` (ticker, company), not a hardcoded list -- so resolution
    only ever matches something retrieval could actually find."""

    company: str  # raw DB value, e.g. "antares-pharma-inc"
    ticker: str | None = None


@dataclass(frozen=True)
class ResolvedFilters:
    """Result of resolving a question against the known-entities list.
    Deliberately does not carry a ticker filter -- see EntityResolver's
    docstring for why. An empty ResolvedFilters() means "nothing matched
    confidently, apply no filter", not "filter to nothing"."""

    company: list[str] | None = None
    fiscal_year: int | None = None
    matched_entity: str | None = None  # for logging only

    def as_filters_dict(self) -> dict:
        out = {}
        if self.company:
            out["company"] = self.company
        if self.fiscal_year is not None:
            out["fiscal_year"] = self.fiscal_year
        return out


class EntityResolver:
    """Resolves free-text company/ticker/year mentions in a question against
    the set of companies actually loaded in the corpus, so retrieval can be
    scoped instead of always searching the full unfiltered corpus (finding
    2.6 -- see chat_service.py, which previously called generate_answer()
    with no filters at all).

    Two things this deliberately does NOT do, both informed by real data
    from the loaded corpus:

    1. It never emits a `ticker` filter, only `company`. `search_similar()`
       ANDs together whatever filters are non-None. ticker completeness is
       uneven across the corpus -- confirmed real: every one of Antares
       Pharma's 173 loaded chunks has ticker = NULL (see
       rag/bulk_load_results_supabase.csv, n_ticker_missing=173/173),
       while `company` is populated on every row. Emitting both would
       silently zero out retrieval for any company with incomplete ticker
       data via `ticker = ANY(...) AND company = ANY(...)` evaluating to
       NULL/false on the ticker side. A ticker mention in the question is
       still used -- as a strong signal for *which* known company to
       resolve to -- just not as a second, separately-ANDed DB filter.

    2. It fails open. If nothing matches confidently, no filter is applied
       and behavior is identical to before this resolver existed. Scoping
       retrieval to a wrong or empty match is worse than not scoping it at
       all -- the DB-level filter here is an exact match against the
       resolved value, not itself fuzzy, so a bad resolution doesn't
       degrade gracefully, it returns zero rows.
    """

    def __init__(self, known_entities: list[KnownEntity]) -> None:
        self._entities = [e for e in known_entities if e.company]
        self._prepared = [
            (
                entity,
                _core_tokens(_normalize(entity.company).split()),
                (entity.ticker or "").upper(),
            )
            for entity in self._entities
        ]

    def resolve(self, question: str) -> ResolvedFilters:
        if not self._prepared:
            return ResolvedFilters()

        q_upper = question.upper()
        q_tokens = _normalize(question).split()

        best_entity: KnownEntity | None = None
        best_score = 0.0

        for entity, company_tokens, ticker_upper in self._prepared:
            # Exact whole-word ticker match is a strong, low-noise signal on
            # its own -- tickers are short (1-5 chars), so fuzzy-matching
            # them the way company names are fuzzy-matched would produce
            # false positives (e.g. "AAL" fuzzy-matching "AAOI" or "AAP").
            if ticker_upper and re.search(rf"\b{re.escape(ticker_upper)}\b", q_upper):
                best_entity = entity
                best_score = 1.0
                break

            score = _core_match_score(q_tokens, company_tokens)
            if score > best_score:
                best_score = score
                best_entity = entity

        if best_entity is None or best_score < _COMPANY_MATCH_THRESHOLD:
            return ResolvedFilters()  # fail open -- see class docstring

        fiscal_year = None
        year_match = _YEAR_PATTERN.search(question)
        if year_match:
            fiscal_year = int(year_match.group(0))

        return ResolvedFilters(
            company=[best_entity.company],
            fiscal_year=fiscal_year,
            matched_entity=best_entity.company,
        )
