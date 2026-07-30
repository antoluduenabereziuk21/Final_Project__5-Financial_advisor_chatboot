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

        return {
            "answer": result["answer"],
            "sources": result.get("sources", []),
            "conversation_id": resolved_conversation_id,
        }
