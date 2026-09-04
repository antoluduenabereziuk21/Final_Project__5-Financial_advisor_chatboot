from __future__ import annotations

from rag.retrieval.entity_resolver import EntityResolver, KnownEntity, ResolvedFilters

_KNOWN = [
    KnownEntity(company="antares-pharma-inc", ticker=None),  # ticker NULL in DB, real case
    KnownEntity(company="applied-optoelectronics-inc", ticker="AAOI"),
    KnownEntity(company="american-airlines-group-inc", ticker="AAL"),
    KnownEntity(company="apple-inc", ticker="AAPL"),
]


def test_no_known_entities_fails_open():
    resolver = EntityResolver([])
    assert resolver.resolve("¿Cómo le fue a Apple en 2024?") == ResolvedFilters()


def test_exact_ticker_mention_resolves_company_but_not_ticker_filter():
    resolver = EntityResolver(_KNOWN)
    result = resolver.resolve("What was AAOI's RMB revenue percentage in fiscal 2022?")
    # Only `company` is ever emitted -- see EntityResolver's docstring on why
    # a ticker filter is deliberately never set (uneven ticker completeness,
    # e.g. Antares' 173/173 NULL tickers -- an AND with a NULL ticker column
    # would silently zero out that company's retrieval).
    assert result.company == ["applied-optoelectronics-inc"]
    assert result.fiscal_year == 2022


def test_ticker_substring_of_another_ticker_does_not_false_match():
    # "AAL" must not fuzzy-match "AAOI" or "AAPL" -- exact word-boundary
    # match only, since tickers are short enough that fuzzy matching them
    # would be noise, not signal.
    resolver = EntityResolver(_KNOWN)
    result = resolver.resolve("How did AAL perform in 2022?")
    assert result.company == ["american-airlines-group-inc"]


def test_fuzzy_company_name_match_without_ticker_mention():
    resolver = EntityResolver(_KNOWN)
    result = resolver.resolve(
        "¿Qué pago recibió Antares Pharma de LEO Pharma a principios de 2014?"
    )
    assert result.company == ["antares-pharma-inc"]
    assert result.fiscal_year == 2014


def test_company_name_slug_variant_still_matches():
    resolver = EntityResolver(_KNOWN)
    result = resolver.resolve("Tell me about American Airlines Group's fleet depreciation.")
    assert result.company == ["american-airlines-group-inc"]


def test_unrelated_question_fails_open_no_filter():
    resolver = EntityResolver(_KNOWN)
    result = resolver.resolve("What is the capital of France?")
    assert result == ResolvedFilters()


def test_generic_financial_question_with_no_company_mention_fails_open():
    resolver = EntityResolver(_KNOWN)
    result = resolver.resolve("¿Cuál es la mejor acción para comprar este año?")
    assert result.company is None


def test_year_without_confident_company_match_is_not_applied_alone():
    # A bare year mention with no resolvable company must not filter on
    # fiscal_year alone -- that would scope retrieval to "any company, this
    # year" instead of leaving it unfiltered, which is a worse failure mode
    # than not filtering at all.
    resolver = EntityResolver(_KNOWN)
    result = resolver.resolve("What happened in the market in 2022?")
    assert result.fiscal_year is None
    assert result.company is None


def test_generic_industry_mention_does_not_false_match_a_similarly_named_company():
    # Regression test for a real false positive found while building this:
    # an earlier whole-string sliding-window scorer matched "What are
    # general trends in the pharma industry?" against "antares-pharma-inc"
    # at 0.75 (above the then-threshold of 0.72), because the filler word
    # "the" coincidentally shared enough characters with "antares" once
    # concatenated with an exact match on "pharma". A generic question with
    # no company in mind must not get scoped to one specific company.
    resolver = EntityResolver(_KNOWN)
    result = resolver.resolve("What are general trends in the pharma industry?")
    assert result.company is None


def test_disambiguates_similarly_prefixed_companies():
    # "Applied Optoelectronics" and "Applied Materials" share a first word;
    # each question must resolve to its own company, not either one, not
    # neither.
    known = _KNOWN + [KnownEntity(company="applied-materials-inc", ticker="AMAT")]
    resolver = EntityResolver(known)
    assert resolver.resolve("What was Applied Optoelectronics revenue in 2022?").company == [
        "applied-optoelectronics-inc"
    ]
    assert resolver.resolve("What was Applied Materials revenue in 2022?").company == [
        "applied-materials-inc"
    ]


def test_as_filters_dict_omits_unset_fields():
    assert ResolvedFilters().as_filters_dict() == {}
    assert ResolvedFilters(company=["apple-inc"]).as_filters_dict() == {
        "company": ["apple-inc"]
    }
    assert ResolvedFilters(company=["apple-inc"], fiscal_year=2024).as_filters_dict() == {
        "company": ["apple-inc"],
        "fiscal_year": 2024,
    }
