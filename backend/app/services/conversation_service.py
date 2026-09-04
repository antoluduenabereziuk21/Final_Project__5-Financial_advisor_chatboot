from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

# Deferred into TYPE_CHECKING for the same reason as ChatService's
# EntityResolver import (see chat_service.py): app.main imports this module
# before it inserts the project root onto sys.path.
if TYPE_CHECKING:
    from app.repositories.conversation_repository import ConversationRepository


class ConversationService:
    def __init__(self, repository: ConversationRepository | None = None) -> None:
        self._repository = repository
        self._conversations: dict[str, list[dict[str, Any]]] = {}

    async def ensure_conversation_id(self, conversation_id: str | None) -> str:
        if self._repository is not None:
            return await self._repository.ensure_conversation(conversation_id)

        return conversation_id or str(uuid.uuid4())

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
        sources: list[dict[str, Any]] | None = None,
        confidence_flag: str | None = None,
        retrieval_meta: dict[str, Any] | None = None,
    ) -> str:
        if self._repository is not None:
            return await self._repository.save_turn(
                conversation_id=conversation_id,
                user_message=user_message,
                assistant_message=assistant_message,
                sources=sources,
                confidence_flag=confidence_flag,
                retrieval_meta=retrieval_meta,
            )

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
