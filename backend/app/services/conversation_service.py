from collections.abc import Iterable


class ConversationService:
    def __init__(self) -> None:
        self._conversations: dict[str, list[dict[str, str]]] = {}

    def ensure_conversation_id(self, conversation_id: str | None) -> str:
        if conversation_id:
            return conversation_id

        # Replace this in production with PostgreSQL-backed conversation IDs and
        # persisted threads so history survives process restarts.
        import uuid

        return str(uuid.uuid4())

    def get_history(self, conversation_id: str) -> list[dict[str, str]]:
        return list(self._conversations.get(conversation_id, []))

    def save_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        conversation = self._conversations.setdefault(conversation_id, [])
        conversation.append({"role": "user", "content": user_message})
        conversation.append({"role": "assistant", "content": assistant_message})

    def extend_history(
        self,
        conversation_id: str,
        messages: Iterable[dict[str, str]],
    ) -> None:
        conversation = self._conversations.setdefault(conversation_id, [])
        conversation.extend(messages)
