from collections.abc import Iterable
from typing import Any

from app.repositories.conversation_repository import ConversationRepository


class ConversationService:
    def __init__(self, repository: ConversationRepository | None = None) -> None:
        self._repository = repository
        self._conversations: dict[str, list[dict[str, Any]]] = {}

    def ensure_conversation_id(self, conversation_id: str | None) -> str:
        if self._repository is not None:
            return self._repository.normalize_conversation_id(conversation_id)

        if conversation_id:
            try:
                import uuid

                return str(uuid.UUID(conversation_id))
            except ValueError:
                import uuid

                return str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"financial-advisor-chat:{conversation_id}",
                    )
                )

        import uuid

        return str(uuid.uuid4())

    async def get_history(self, conversation_id: str) -> list[dict[str, str]]:
        if self._repository is not None:
            return await self._repository.get_history(conversation_id)

        history = self._conversations.get(conversation_id, [])
        return [
            {
                "role": str(turn.get("role", "")),
                "content": str(turn.get("content", "")),
            }
            for turn in history
        ]

    async def save_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        user_id: int | None = None,
    ) -> str:
        if self._repository is not None:
            return await self._repository.save_turn(
                conversation_id=conversation_id,
                user_message=user_message,
                assistant_message=assistant_message,
                user_id=user_id,
            )

        import uuid

        conversation = self._conversations.setdefault(conversation_id, [])
        user_message_id = str(uuid.uuid4())
        assistant_message_id = str(uuid.uuid4())
        conversation.append(
            {"id": user_message_id, "role": "user", "content": user_message}
        )
        conversation.append(
            {
                "id": assistant_message_id,
                "role": "assistant",
                "content": assistant_message,
            }
        )
        return assistant_message_id

    def extend_history(
        self,
        conversation_id: str,
        messages: Iterable[dict[str, Any]],
    ) -> None:
        conversation = self._conversations.setdefault(conversation_id, [])
        conversation.extend(messages)
