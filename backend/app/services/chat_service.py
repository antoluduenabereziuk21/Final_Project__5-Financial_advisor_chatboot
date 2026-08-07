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

        self._conversation_service.save_turn(
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
                normalized_sources.append({"title": title, **source})

        return {
            "answer": result["answer"],
            "sources": normalized_sources,
            "conversation_id": resolved_conversation_id,
        }
