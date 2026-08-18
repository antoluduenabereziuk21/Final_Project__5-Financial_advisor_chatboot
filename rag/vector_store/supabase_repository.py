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

        headers = {
            "apikey": self._key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(
            timeout=self._timeout
        ) as client:
            response = await client.post(
                f"{self._url}/rest/v1/rpc/match_rag_chunks",
                headers=headers,
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
                accounting_standard=row.get(
                    "accounting_standard"
                ),
                canonical_section=row.get(
                    "canonical_section"
                ),
                source_file=row.get("source_file", ""),
                page_start=row.get("page_start"),
                page_end=row.get("page_end"),
                company_name_mismatch=row.get(
                    "company_name_mismatch"
                ),
            )
            for row in rows
        ]
