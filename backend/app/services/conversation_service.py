from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ConversationRecord, MessageRecord


class ConversationService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def ensure_conversation_id(self, conversation_id: str | None) -> str:
        if conversation_id:
            return conversation_id

        return str(uuid4())

    async def get_history(self, conversation_id: str) -> list[dict[str, str]]:
        async with self._session_factory() as session:
            statement = (
                select(MessageRecord.role, MessageRecord.content)
                .where(MessageRecord.conversation_id == conversation_id)
                .order_by(MessageRecord.created_at.asc())
            )
            rows = (await session.execute(statement)).all()

        return [
            {
                "role": role,
                "content": content,
            }
            for role, content in rows
        ]

    async def list_conversations(self, limit: int = 20) -> list[dict[str, str | None]]:
        async with self._session_factory() as session:
            statement = (
                select(ConversationRecord)
                .order_by(ConversationRecord.updated_at.desc())
                .limit(limit)
            )
            records = (await session.execute(statement)).scalars().all()

        return [
            {
                "conversation_id": record.id,
                "user_id": record.user_id,
                "created_at": record.created_at.isoformat(),
                "updated_at": record.updated_at.isoformat(),
            }
            for record in records
        ]

    async def get_conversation_detail(self, conversation_id: str) -> dict | None:
        async with self._session_factory() as session:
            conversation = await session.get(ConversationRecord, conversation_id)
            if conversation is None:
                return None

            statement = (
                select(MessageRecord)
                .where(MessageRecord.conversation_id == conversation_id)
                .order_by(MessageRecord.created_at.asc())
            )
            messages = (await session.execute(statement)).scalars().all()

        return {
            "conversation_id": conversation.id,
            "user_id": conversation.user_id,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": [
                {
                    "message_id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                }
                for message in messages
            ],
        }

    async def save_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> str:
        assistant_message_id = str(uuid4())

        async with self._session_factory() as session:
            await self._ensure_conversation_exists(session, conversation_id)

            session.add(
                MessageRecord(
                    id=str(uuid4()),
                    conversation_id=conversation_id,
                    role="user",
                    content=user_message,
                )
            )
            session.add(
                MessageRecord(
                    id=assistant_message_id,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_message,
                )
            )
            await session.commit()

        return assistant_message_id

    async def ensure_conversation_exists(
        self,
        conversation_id: str,
        user_id: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            await self._ensure_conversation_exists(
                session,
                conversation_id,
                user_id=user_id,
            )
            await session.commit()

    async def _ensure_conversation_exists(
        self,
        session: AsyncSession,
        conversation_id: str,
        user_id: str | None = None,
    ) -> None:
        existing_conversation = await session.get(ConversationRecord, conversation_id)
        if existing_conversation is not None:
            existing_conversation.updated_at = datetime.now(UTC)
            if user_id and not existing_conversation.user_id:
                existing_conversation.user_id = user_id
            return

        session.add(
            ConversationRecord(
                id=conversation_id,
                user_id=user_id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
