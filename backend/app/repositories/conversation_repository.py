from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rag.vector_store.client import VectorDbClient


def _to_jsonb(value: Any) -> str | None:
    return None if value is None else json.dumps(value)


class ConversationRepository:
    """Persiste conversations/chat_messages/message_feedback en Postgres.

    Reutiliza el pool ya conectado por `VectorDbClient` (ver backend/app/main.py
    lifespan) en vez de abrir una conexion propia -- el intento anterior de esto
    (revertido, ver commit ad04386) abria un `VectorDbClient` adicional en
    paralelo al que ya usa el retrieval de pgvector, duplicando el pool contra
    la misma base de datos.
    """

    def __init__(self, client: VectorDbClient) -> None:
        self._client = client

    @staticmethod
    def _normalize_conversation_id(conversation_id: str | None) -> str | None:
        """Devuelve un UUID valido en formato canonico, o None si `conversation_id`
        esta ausente o no es un UUID real.

        A diferencia del intento anterior, un valor no-UUID NO se hashea a un id
        determinista (`uuid5`) -- eso permitia que un id de cliente arbitrario
        se remapeara silenciosamente a una conversacion ajena si dos clientes
        elegian el mismo string. El frontend actual solo reenvia el
        conversation_id que el propio servidor emitio, asi que un valor no-UUID
        aqui solo puede ser un cliente antiguo/malformado -- se trata como
        "no hay conversacion todavia" y se crea una nueva.
        """
        if not conversation_id:
            return None
        try:
            return str(uuid.UUID(conversation_id))
        except ValueError:
            return None

    async def ensure_conversation(
        self,
        conversation_id: str | None,
        user_id: int | None = None,
        title: str = "Nueva conversacion",
    ) -> str:
        normalized_id = self._normalize_conversation_id(conversation_id)

        async with self._client.pool.acquire() as conn:
            if normalized_id is not None:
                row = await conn.fetchrow(
                    """
                    INSERT INTO conversations (id, user_id, title)
                    VALUES ($1::uuid, $2, $3)
                    ON CONFLICT (id) DO UPDATE SET
                        user_id = COALESCE(conversations.user_id, EXCLUDED.user_id),
                        updated_at = NOW()
                    RETURNING id
                    """,
                    normalized_id,
                    user_id,
                    title,
                )
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO conversations (user_id, title)
                    VALUES ($1, $2)
                    RETURNING id
                    """,
                    user_id,
                    title,
                )

        return str(row["id"])

    async def get_history(self, conversation_id: str) -> list[dict[str, str]]:
        normalized_id = self._normalize_conversation_id(conversation_id)
        if normalized_id is None:
            return []

        async with self._client.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT role, content
                FROM chat_messages
                WHERE conversation_id = $1::uuid
                ORDER BY id ASC
                """,
                normalized_id,
            )

        return [
            {"role": str(row["role"]), "content": str(row["content"])}
            for row in rows
        ]

    async def save_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        sources: list[dict[str, Any]] | None = None,
        confidence_flag: str | None = None,
        retrieval_meta: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> str:
        """Persiste ambos turnos de la conversacion (user + assistant).

        `conversation_id` debe ser un UUID ya resuelto por
        `ConversationService.ensure_conversation_id` (que a su vez llama a
        `ensure_conversation` arriba) -- este metodo no crea la conversacion,
        solo agrega mensajes a una que ya existe. Devuelve el id del mensaje
        del assistant.
        """
        resolved_conversation_id = self._normalize_conversation_id(conversation_id)
        if resolved_conversation_id is None:
            raise ValueError(
                f"save_turn recibio un conversation_id invalido: {conversation_id!r} "
                "-- debe resolverse con ensure_conversation_id antes de guardar turnos"
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
                    INSERT INTO chat_messages
                        (conversation_id, role, content, sources, confidence_flag, retrieval_meta)
                    VALUES ($1::uuid, 'assistant', $2, $3::jsonb, $4, $5::jsonb)
                    RETURNING id
                    """,
                    resolved_conversation_id,
                    assistant_message,
                    _to_jsonb(sources),
                    confidence_flag,
                    _to_jsonb(retrieval_meta),
                )

        if assistant_row is None:
            raise RuntimeError("Failed to persist assistant message")

        return str(assistant_row["id"])

    async def save_feedback(
        self,
        message_id: str,
        conversation_id: str,
        rating: str,
        reason: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        async with self._client.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO message_feedback
                    (message_id, conversation_id, rating, reason, user_id)
                VALUES ($1, $2::uuid, $3, $4, $5)
                RETURNING id, created_at
                """,
                int(message_id),
                conversation_id,
                rating,
                reason,
                int(user_id) if user_id else None,
            )

        return {
            "feedback_id": str(row["id"]),
            "conversation_id": conversation_id,
            "message_id": message_id,
            "rating": rating,
            "reason": reason,
            "user_id": user_id,
            "created_at": row["created_at"].isoformat(),
        }

    async def list_feedback(self, conversation_id: str) -> list[dict[str, Any]]:
        normalized_id = self._normalize_conversation_id(conversation_id)
        if normalized_id is None:
            return []

        async with self._client.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, message_id, rating, reason, user_id, created_at
                FROM message_feedback
                WHERE conversation_id = $1::uuid
                ORDER BY id ASC
                """,
                normalized_id,
            )

        return [
            {
                "feedback_id": str(row["id"]),
                "conversation_id": conversation_id,
                "message_id": str(row["message_id"]),
                "rating": row["rating"],
                "reason": row["reason"],
                "user_id": str(row["user_id"]) if row["user_id"] is not None else None,
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]
