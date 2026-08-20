from collections.abc import Iterable
from typing import Any


class ConversationService:
    def __init__(self) -> None:
        self._conversations: dict[str, list[dict[str, Any]]] = {}

    def ensure_conversation_id(self, conversation_id: str | None) -> str:
        if conversation_id:
            return conversation_id

        # Replace this in production with PostgreSQL-backed conversation IDs and
        # persisted threads so history survives process restarts.
        import uuid

        return str(uuid.uuid4())

    def get_history(self, conversation_id: str) -> list[dict[str, str]]:
        history = self._conversations.get(conversation_id, [])
        return [
            {
                "role": str(turn.get("role", "")),
                "content": str(turn.get("content", "")),
            }
            for turn in history
        ]

    def save_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> str:
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
