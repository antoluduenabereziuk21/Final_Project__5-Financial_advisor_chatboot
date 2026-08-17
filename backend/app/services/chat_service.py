from datetime import UTC, datetime
from typing import Any

from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService


class ChatService:
    def __init__(
        self,
        rag_service: RAGService,
        conversation_service: ConversationService,
    ) -> None:
        self._rag_service = rag_service
        self._conversation_service = conversation_service
        self._feedback_by_conversation: dict[str, list[dict[str, Any]]] = {}
        self._source_index: dict[str, dict[str, Any]] = {}

    async def handle_message(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> dict:
        resolved_conversation_id = self._conversation_service.ensure_conversation_id(
            conversation_id
        )
        conversation_history = self._conversation_service.get_history(
            resolved_conversation_id
        )

        result = await self._rag_service.generate_answer(
            question=message,
            conversation_history=conversation_history,
        )

        message_id = self._conversation_service.save_turn(
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

                chunk_id = normalized_source.get("chunk_id")
                if isinstance(chunk_id, str) and chunk_id:
                    self._source_index[chunk_id] = {
                        **normalized_source,
                        "conversation_id": resolved_conversation_id,
                    }

        return {
            "answer": result["answer"],
            "sources": normalized_sources,
            "conversation_id": resolved_conversation_id,
            "message_id": message_id,
        }

    def save_feedback(
        self,
        conversation_id: str,
        message_id: str,
        rating: str,
        reason: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        import uuid

        feedback = {
            "feedback_id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "message_id": message_id,
            "rating": rating,
            "reason": reason,
            "user_id": user_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        conversation_feedback = self._feedback_by_conversation.setdefault(
            conversation_id, []
        )
        conversation_feedback.append(feedback)
        return feedback

    def list_feedback(self, conversation_id: str) -> list[dict[str, Any]]:
        return list(self._feedback_by_conversation.get(conversation_id, []))

    def get_source_detail(self, chunk_id: str) -> dict[str, Any] | None:
        return self._source_index.get(chunk_id)
