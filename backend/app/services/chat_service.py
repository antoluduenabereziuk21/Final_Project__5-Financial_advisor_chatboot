from __future__ import annotations

# datetime.UTC was added in Python 3.11 -- this project's venv has been seen
# running Python 3.9 (see rag/SETUP.md), where that import raises
# ImportError before app.main can even load. timezone.utc is the same value
# and works on every Python 3.x version, so it's used here regardless of
# which interpreter ends up running this.
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService

# Lazy/type-check-only imports, deliberately not top-level runtime imports:
# backend/app/main.py imports ChatService (this module) before it inserts
# the project root onto sys.path (that insertion happens further down in
# main.py, and every other rag.* import from backend/app/* is already
# deferred into a function body for the same reason -- see main.py's
# lifespan()). A top-level import here breaks at process startup with
# "ModuleNotFoundError: No module named 'rag'" (confirmed real
# 2026-08-21). `from __future__ import annotations` above means these
# annotations are never evaluated at runtime, so this only needs to be
# visible to type checkers.
if TYPE_CHECKING:
    from app.repositories.conversation_repository import ConversationRepository
    from rag.retrieval.entity_resolver import EntityResolver
    from rag.retrieval.retriever import VectorSearchRepository


class ChatService:
    def __init__(
        self,
        rag_service: RAGService,
        conversation_service: ConversationService,
        entity_resolver: EntityResolver | None = None,
        conversation_repository: ConversationRepository | None = None,
        vector_repo: VectorSearchRepository | None = None,
    ) -> None:
        self._rag_service = rag_service
        self._conversation_service = conversation_service
        self._entity_resolver = entity_resolver
        # Backs /api/chat/feedback when Postgres is connected (see main.py);
        # falls back to the in-memory dict below otherwise, same degradation
        # pattern as ConversationService/RAGService use for their own state.
        self._conversation_repository = conversation_repository
        # Backs /api/sources/{chunk_id} via rag_chunks.get_by_id when
        # available (see get_source_detail below); falls back to the
        # in-memory index otherwise.
        self._vector_repo = vector_repo
        self._feedback_by_conversation: dict[str, list[dict[str, Any]]] = {}
        self._source_index: dict[str, dict[str, Any]] = {}

    async def handle_message(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> dict:
        resolved_conversation_id = await self._conversation_service.ensure_conversation_id(
            conversation_id
        )
        conversation_history = await self._conversation_service.get_history(
            resolved_conversation_id
        )

        # 2.6: scope retrieval to a company/fiscal_year mention extracted
        # from the question, when one resolves confidently against the
        # companies actually loaded in the corpus. Previously this call
        # never passed filters at all, so every query -- however specific
        # its wording -- searched the full unfiltered corpus (confirmed
        # real: this is what produced the AAOI wrong-fiscal-year retrieval
        # and AAL no-retrieval failures on 2026-08-21). entity_resolver is
        # None when no RAG backend connected at startup (see main.py); in
        # that case RAGService itself short-circuits before filters matter.
        filters = None
        if self._entity_resolver is not None:
            resolved = self._entity_resolver.resolve(message)
            filters = resolved.as_filters_dict() or None

        result = await self._rag_service.generate_answer(
            question=message,
            conversation_history=conversation_history,
            filters=filters,
        )

        sources = result.get("sources", [])
        normalized_sources = []
        for source in sources:
            if isinstance(source, dict):
                # Fallback chain for display purposes only. This must never
                # resolve to a specific, fabricated-looking source name -- a
                # missing title means retrieval didn't return real metadata,
                # and the label needs to say that plainly rather than
                # impersonate a real citation (previously defaulted to the
                # hardcoded "Apple Annual Report 2025").
                title = (
                    source.get("title")
                    or source.get("source_file")
                    or source.get("company")
                    or source.get("chunk_id")
                    or "Unknown source"
                )
                if title == "unknown":
                    title = "Unknown source"
                normalized_source = {"title": title, **source}
                normalized_sources.append(normalized_source)

                chunk_id = normalized_source.get("chunk_id")
                if chunk_id is not None:
                    self._source_index[str(chunk_id)] = {
                        **normalized_source,
                        "conversation_id": resolved_conversation_id,
                    }

        message_id = await self._conversation_service.save_turn(
            conversation_id=resolved_conversation_id,
            user_message=message,
            assistant_message=result["answer"],
            sources=normalized_sources,
            confidence_flag=result.get("confidence_flag"),
            retrieval_meta=result.get("retrieval_meta"),
        )

        return {
            "answer": result["answer"],
            "sources": normalized_sources,
            "conversation_id": resolved_conversation_id,
            "message_id": message_id,
        }

    async def save_feedback(
        self,
        conversation_id: str,
        message_id: str,
        rating: str,
        reason: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        if self._conversation_repository is not None:
            return await self._conversation_repository.save_feedback(
                message_id=message_id,
                conversation_id=conversation_id,
                rating=rating,
                reason=reason,
                user_id=user_id,
            )

        import uuid

        feedback = {
            "feedback_id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "message_id": message_id,
            "rating": rating,
            "reason": reason,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        conversation_feedback = self._feedback_by_conversation.setdefault(
            conversation_id, []
        )
        conversation_feedback.append(feedback)
        return feedback

    async def list_feedback(self, conversation_id: str) -> list[dict[str, Any]]:
        if self._conversation_repository is not None:
            return await self._conversation_repository.list_feedback(conversation_id)

        return list(self._feedback_by_conversation.get(conversation_id, []))

    async def get_source_detail(self, chunk_id: str) -> dict[str, Any] | None:
        # chunk_id in sources[] is rag_chunks.id (see rag/retrieval/retriever.py)
        # -- when a vector repo that supports lookup by id is connected, query
        # the real row instead of relying on a process-local cache. Repos that
        # only support retrieval over HTTPS (e.g. Supabase, see
        # rag/vector_store/supabase_repository.py) don't implement get_by_id;
        # fall back to the in-memory index for those, same as before.
        if self._vector_repo is not None and hasattr(self._vector_repo, "get_by_id"):
            try:
                numeric_chunk_id = int(chunk_id)
            except ValueError:
                numeric_chunk_id = None

            if numeric_chunk_id is not None:
                record = await self._vector_repo.get_by_id(numeric_chunk_id)
                if record is not None:
                    title = record.source_file or record.company or str(record.id) or "Unknown source"
                    return {
                        "chunk_id": str(record.id),
                        "title": title,
                        "company": record.company,
                        "ticker": record.ticker,
                        "fiscal_year": record.fiscal_year,
                        "form_type": record.form_type,
                        "accounting_standard": record.accounting_standard,
                        "canonical_section": record.canonical_section,
                        "source_file": record.source_file,
                        "page_start": record.page_start,
                        "page_end": record.page_end,
                        "relevance_score": None,
                        "text_snippet": record.content[:300] if record.content else None,
                        "conversation_id": None,
                    }

        return self._source_index.get(chunk_id)
