import asyncio

import pytest

from rag.llm import generator


@pytest.fixture(autouse=True)
def _reset_provider():
    """generator._LLM_PROVIDER is module-level global state set by
    configure() -- reset it around each test so tests don't leak into each
    other regardless of run order (see rag/llm/issues_find.md's note on this
    being config-as-global-mutable-state)."""
    original = generator._LLM_PROVIDER
    generator._LLM_PROVIDER = None
    yield
    generator._LLM_PROVIDER = original


def _source(**overrides):
    base = {"relevance_score": 0.8, "company_name_mismatch": False}
    base.update(overrides)
    return base


def test_no_sources_is_entity_not_found():
    assert generator._compute_confidence_flag([], "¿Cómo le fue a Apple?") == "entity_not_found"


def test_low_score_is_low_confidence_not_unverified_source():
    # Weak retrieval score takes precedence over an unverified company match
    # -- if the match itself is bad, the attribution question is moot.
    sources = [_source(relevance_score=0.1, company_name_mismatch=None)]
    assert generator._compute_confidence_flag(sources, "¿Cómo le fue a Apple?") == "low_confidence"


def test_subjective_question_is_subjective_no_verdict():
    sources = [_source()]
    assert (
        generator._compute_confidence_flag(sources, "¿Cuál es la mejor acción para comprar?")
        == "subjective_no_verdict"
    )


def test_unverified_company_match_gets_its_own_flag():
    # company_name_mismatch is None ("never checked") must NOT be reported as
    # plain low_confidence -- it's a distinct condition (unverified
    # attribution, not weak retrieval) and is handled differently downstream.
    sources = [_source(company_name_mismatch=None)]
    assert generator._compute_confidence_flag(sources, "¿Cómo le fue a Apple?") == "unverified_source"


def test_confirmed_match_is_ok():
    sources = [_source(company_name_mismatch=False)]
    assert generator._compute_confidence_flag(sources, "¿Cómo le fue a Apple?") == "ok"


def test_unverified_source_from_a_different_company_does_not_taint_the_flag():
    # Regression test for the real 2026-08-21 case: retrieval (unfiltered by
    # company/ticker -- finding 2.6) returned the correct, clean, highest-
    # scoring Antares Pharma chunk alongside lower-scoring, uncited chunks
    # from unrelated companies (Ascendis, Argenx) that happen to share
    # vocabulary with the question and have company_name_mismatch IS NULL.
    # The top-scoring (and only actually-cited) source is clean, so this
    # must resolve "ok", not "unverified_source".
    sources = [
        _source(
            company="antares-pharma-inc",
            relevance_score=0.5281,
            company_name_mismatch=False,
        ),
        _source(
            company="ascendis-pharma-as",
            relevance_score=0.5264,
            company_name_mismatch=None,
        ),
        _source(
            company="argenx",
            relevance_score=0.5169,
            company_name_mismatch=None,
        ),
    ]
    assert (
        generator._compute_confidence_flag(sources, "¿Qué pago recibió Antares Pharma de LEO Pharma?")
        == "ok"
    )


def test_unverified_source_from_the_same_company_still_triggers_the_flag():
    # The scoping fix must not blind the flag to a genuine same-company
    # uncertainty -- if the top-scoring chunk's own company has an unchecked
    # sibling chunk in the retrieved set, that's still a real attribution
    # question about the company actually being cited.
    sources = [
        _source(
            company="antares-pharma-inc",
            relevance_score=0.53,
            company_name_mismatch=False,
        ),
        _source(
            company="antares-pharma-inc",
            relevance_score=0.50,
            company_name_mismatch=None,
        ),
    ]
    assert (
        generator._compute_confidence_flag(sources, "¿Cómo le fue a Antares Pharma?")
        == "unverified_source"
    )


def test_unverified_source_answer_carries_a_disclaimer_even_without_an_llm():
    """The disclaimer must be code-enforced, not dependent on the LLM
    choosing to include it -- verify it's present even on the no-provider
    dev fallback path, where there's no LLM to (not) comply."""
    sources = [_source(company_name_mismatch=None)]

    answer, flag = asyncio.run(generator.generate("¿Cómo le fue a Apple en 2025?", sources))

    assert flag == "unverified_source"
    assert "verification process" in answer


def test_ok_answer_has_no_disclaimer():
    sources = [_source(company_name_mismatch=False)]

    answer, flag = asyncio.run(generator.generate("¿Cómo le fue a Apple en 2025?", sources))

    assert flag == "ok"
    assert "verification process" not in answer


def test_notice_is_not_duplicated_if_already_present():
    already = f"Some answer. {generator._UNVERIFIED_SOURCE_NOTICE}"
    assert generator._with_unverified_source_notice(already) == already
