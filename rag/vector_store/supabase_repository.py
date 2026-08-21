from __future__ import annotations

import os

import httpx

from rag.vector_store.models import SearchParams, SearchResult


class SupabaseVectorRepository:
    """Vector retrieval through Supabase REST/RPC over HTTPS."""

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._url = (
            supabase_url
            or os.getenv("SUPABASE_URL", "")
        ).rstrip("/")

        self._key = (
            supabase_key
            or os.getenv("SUPABASE_KEY", "")
        )

        self._timeout = timeout

        if not self._url:
            raise ValueError("SUPABASE_URL is not configured")

        if not self._key:
            raise ValueError("SUPABASE_KEY is not configured")

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._key,
            "Content-Type": "application/json",
        }

    async def search_similar(
        self,
        params: SearchParams,
    ) -> list[SearchResult]:
        payload = {
            "query_embedding": params.query_embedding,
            "match_count": params.top_k,
            "filter_ticker": params.ticker,
            "filter_company": params.company,
            "filter_fiscal_year": params.fiscal_year,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._url}/rest/v1/rpc/match_rag_chunks",
                headers=self._headers(),
                json=payload,
            )

            response.raise_for_status()
            rows = response.json()

        return [
            SearchResult(
                id=row["id"],
                content=row["content"],
                similarity=float(row["similarity"]),
                ticker=row["ticker"],
                company=row["company"],
                fiscal_year=row["fiscal_year"],
                form_type=row.get("form_type"),
                accounting_standard=row.get("accounting_standard"),
                canonical_section=row.get("canonical_section"),
                source_file=row.get("source_file", ""),
                page_start=row.get("page_start"),
                page_end=row.get("page_end"),
                company_name_mismatch=row.get(
                    "company_name_mismatch"
                ),
            )
            for row in rows
        ]

    async def list_companies(self) -> list[dict]:
        """Distinct (ticker, company) pairs actually present in the loaded
        corpus, via Supabase's plain REST table endpoint (not the
        match_rag_chunks RPC -- no embedding search needed here). PostgREST
        doesn't expose SQL DISTINCT through query params, so this fetches
        ticker+company for every `documents` row and de-duplicates
        client-side; documents stays small (~1.7K rows even at full load),
        so one unpaginated fetch is fine, unlike search_similar's per-query
        embedding search against rag_chunks."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{self._url}/rest/v1/documents",
                headers=self._headers(),
                params={"select": "ticker,company", "limit": "10000"},
            )
            response.raise_for_status()
            rows = response.json()

        seen: set[tuple[str | None, str | None]] = set()
        companies: list[dict] = []
        for row in rows:
            key = (row.get("ticker"), row.get("company"))
            if key not in seen:
                seen.add(key)
                companies.append({"ticker": row.get("ticker"), "company": row.get("company")})
        return companies

    async def count(self) -> int:
        """Return the number of indexed chunks visible through Supabase REST."""

        headers = {
            **self._headers(),
            "Prefer": "count=planned",
            "Range": "0-0",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{self._url}/rest/v1/rag_chunks",
                headers=headers,
                params={
                    "select": "id",
                    "limit": "1",
                },
            )

            response.raise_for_status()

        content_range = response.headers.get("content-range", "")

        if "/" not in content_range:
            raise RuntimeError(
                "Supabase did not return an exact row count."
            )

        total = content_range.rsplit("/", 1)[1]

        if total == "*":
            raise RuntimeError(
                "Supabase returned an unknown row count."
            )

        return int(total)
