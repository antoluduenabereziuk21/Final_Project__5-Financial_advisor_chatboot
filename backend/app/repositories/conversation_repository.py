from __future__ import annotations

import uuid
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from rag.vector_store.client import VectorDbClient


class ConversationRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    @staticmethod
    def normalize_conversation_id(conversation_id: str | None) -> str:
        if conversation_id:
            try:
                return str(uuid.UUID(conversation_id))
            except ValueError:
                return str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"financial-advisor-chat:{conversation_id}",
                    )
                )

        return str(uuid.uuid4())

    async def ensure_conversation(
        self,
        conversation_id: str | None,
        user_id: int | None = None,
        title: str = "Nueva conversacion",
    ) -> str:
        resolved_conversation_id = self.normalize_conversation_id(conversation_id)

        async with self._client.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversations (id, user_id, title)
                VALUES ($1::uuid, $2, $3)
                ON CONFLICT (id) DO UPDATE SET
                    user_id = COALESCE(conversations.user_id, EXCLUDED.user_id),
                    updated_at = NOW()
                """,
                resolved_conversation_id,
                user_id,
                title,
            )

        return resolved_conversation_id

    async def get_history(self, conversation_id: str) -> list[dict[str, str]]:
        resolved_conversation_id = self.normalize_conversation_id(conversation_id)

        async with self._client.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT role, content
                FROM chat_messages
                WHERE conversation_id = $1::uuid
                ORDER BY id ASC
                """,
                resolved_conversation_id,
            )

        return [
            {
                "role": str(row["role"]),
                "content": str(row["content"]),
            }
            for row in rows
        ]

    async def save_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        user_id: int | None = None,
    ) -> str:
        resolved_conversation_id = await self.ensure_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        async with self._client.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE conversations
                    SET updated_at = NOW(),
                        user_id = COALESCE(user_id, $2)
                    WHERE id = $1::uuid
                    """,
                    resolved_conversation_id,
                    user_id,
                )

                await conn.execute(
                    """
                    INSERT INTO chat_messages (conversation_id, role, content)
                    VALUES ($1::uuid, 'user', $2)
                    """,
                    resolved_conversation_id,
                    user_message,
                )
                assistant_row = await conn.fetchrow(
                    """
                    INSERT INTO chat_messages (conversation_id, role, content)
                    VALUES ($1::uuid, 'assistant', $2)
                    RETURNING id
                    """,
                    resolved_conversation_id,
                    assistant_message,
                )

        if assistant_row is None:
            raise RuntimeError("Failed to persist assistant message")

        return str(assistant_row["id"])
