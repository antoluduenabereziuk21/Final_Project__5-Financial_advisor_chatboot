from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ChatFeedbackRecord, MessageSourceRecord
from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService


class ChatService:
    def __init__(
        self,
        rag_service: RAGService,
        conversation_service: ConversationService,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._rag_service = rag_service
        self._conversation_service = conversation_service
        self._session_factory = session_factory

    async def handle_message(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> dict:
        resolved_conversation_id = self._conversation_service.ensure_conversation_id(
            conversation_id
        )
        conversation_history = await self._conversation_service.get_history(
            resolved_conversation_id
        )

        result = await self._rag_service.generate_answer(
            question=message,
            conversation_history=conversation_history,
        )

        message_id = await self._conversation_service.save_turn(
            conversation_id=resolved_conversation_id,
            user_message=message,
            assistant_message=result["answer"],
        )

        sources = result.get("sources", [])
        normalized_sources = []
        for source in sources:
            if isinstance(source, dict):
                title = (
                    source.get("title")
                    or source.get("source_file")
                    or source.get("company")
                    or source.get("chunk_id")
                    or "Apple Annual Report 2025"
                )
                if title == "unknown":
                    title = "Apple Annual Report 2025"
                normalized_source = {"title": title, **source}
                normalized_sources.append(normalized_source)

        await self._persist_sources(
            message_id=message_id,
            conversation_id=resolved_conversation_id,
            sources=normalized_sources,
        )

        return {
            "answer": result["answer"],
            "sources": normalized_sources,
            "conversation_id": resolved_conversation_id,
            "message_id": message_id,
        }

    async def _persist_sources(
        self,
        message_id: str,
        conversation_id: str,
        sources: list[dict[str, Any]],
    ) -> None:
        if not sources:
            return

        async with self._session_factory() as session:
            for source in sources:
                chunk_id = source.get("chunk_id")
                if not isinstance(chunk_id, str) or not chunk_id:
                    continue

                session.add(
                    MessageSourceRecord(
                        message_id=message_id,
                        conversation_id=conversation_id,
                        chunk_id=chunk_id,
                        title=str(source.get("title") or chunk_id),
                        company=self._as_optional_str(source.get("company")),
                        ticker=self._as_optional_str(source.get("ticker")),
                        fiscal_year=self._as_optional_int(source.get("fiscal_year")),
                        form_type=self._as_optional_str(source.get("form_type")),
                        accounting_standard=self._as_optional_str(
                            source.get("accounting_standard")
                        ),
                        canonical_section=self._as_optional_str(
                            source.get("canonical_section")
                        ),
                        source_file=self._as_optional_str(source.get("source_file")),
                        page_start=self._as_optional_int(source.get("page_start")),
                        page_end=self._as_optional_int(source.get("page_end")),
                        relevance_score=self._as_optional_float(
                            source.get("relevance_score")
                        ),
                        text_snippet=self._as_optional_str(source.get("text_snippet")),
                    )
                )

            await session.commit()

    async def save_feedback(
        self,
        conversation_id: str,
        message_id: str,
        rating: str,
        reason: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        await self._conversation_service.ensure_conversation_exists(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        feedback_id = str(uuid4())
        created_at = datetime.now(UTC)
        feedback = {
            "feedback_id": feedback_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "rating": rating,
            "reason": reason,
            "user_id": user_id,
            "created_at": created_at.isoformat(),
        }

        async with self._session_factory() as session:
            session.add(
                ChatFeedbackRecord(
                    feedback_id=feedback_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    rating=rating,
                    reason=reason,
                    user_id=user_id,
                    created_at=created_at,
                )
            )
            await session.commit()

        return feedback

    async def list_feedback(self, conversation_id: str) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            statement = (
                select(ChatFeedbackRecord)
                .where(ChatFeedbackRecord.conversation_id == conversation_id)
                .order_by(ChatFeedbackRecord.created_at.asc())
            )
            items = (await session.execute(statement)).scalars().all()

        return [
            {
                "feedback_id": item.feedback_id,
                "conversation_id": item.conversation_id,
                "message_id": item.message_id,
                "rating": item.rating,
                "reason": item.reason,
                "user_id": item.user_id,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ]

    async def list_conversations(self, limit: int = 20) -> list[dict[str, Any]]:
        return await self._conversation_service.list_conversations(limit=limit)

    async def get_conversation_detail(self, conversation_id: str) -> dict[str, Any] | None:
        detail = await self._conversation_service.get_conversation_detail(conversation_id)
        if detail is None:
            return None

        message_ids = [
            str(message.get("message_id"))
            for message in detail["messages"]
            if message.get("message_id")
        ]
        sources_by_message_id = await self._get_sources_by_message_ids(message_ids)

        normalized_messages = []
        for message in detail["messages"]:
            message_id = str(message["message_id"])
            role = str(message["role"])
            normalized_messages.append(
                {
                    "message_id": message_id,
                    "role": role,
                    "content": str(message["content"]),
                    "created_at": str(message["created_at"]),
                    "sources": sources_by_message_id.get(message_id, []),
                }
            )

        return {
            "conversation_id": detail["conversation_id"],
            "user_id": detail["user_id"],
            "created_at": detail["created_at"],
            "updated_at": detail["updated_at"],
            "messages": normalized_messages,
        }

    async def _get_sources_by_message_ids(
        self,
        message_ids: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        if not message_ids:
            return {}

        async with self._session_factory() as session:
            statement = (
                select(MessageSourceRecord)
                .where(MessageSourceRecord.message_id.in_(message_ids))
                .order_by(MessageSourceRecord.created_at.asc())
            )
            rows = (await session.execute(statement)).scalars().all()

        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row.message_id, []).append(
                {
                    "chunk_id": row.chunk_id,
                    "title": row.title,
                    "company": row.company,
                    "ticker": row.ticker,
                    "fiscal_year": row.fiscal_year,
                    "form_type": row.form_type,
                    "accounting_standard": row.accounting_standard,
                    "canonical_section": row.canonical_section,
                    "source_file": row.source_file,
                    "page_start": row.page_start,
                    "page_end": row.page_end,
                    "relevance_score": row.relevance_score,
                    "text_snippet": row.text_snippet,
                }
            )

        return grouped

    async def get_source_detail(self, chunk_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            statement = (
                select(MessageSourceRecord)
                .where(MessageSourceRecord.chunk_id == chunk_id)
                .order_by(desc(MessageSourceRecord.created_at))
                .limit(1)
            )
            source = (await session.execute(statement)).scalars().first()

        if source is None:
            return None

        return {
            "chunk_id": source.chunk_id,
            "title": source.title,
            "company": source.company,
            "ticker": source.ticker,
            "fiscal_year": source.fiscal_year,
            "form_type": source.form_type,
            "accounting_standard": source.accounting_standard,
            "canonical_section": source.canonical_section,
            "source_file": source.source_file,
            "page_start": source.page_start,
            "page_end": source.page_end,
            "relevance_score": source.relevance_score,
            "text_snippet": source.text_snippet,
            "conversation_id": source.conversation_id,
        }

    @staticmethod
    def _as_optional_str(value: Any) -> str | None:
        if value is None:
            return None
        value_str = str(value).strip()
        return value_str or None

    @staticmethod
    def _as_optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
