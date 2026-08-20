from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ConversationRecord(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class MessageRecord(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )


class MessageSourceRecord(Base):
    __tablename__ = "message_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="CASCADE"),
        index=True,
    )
    conversation_id: Mapped[str] = mapped_column(String(128), index=True)
    chunk_id: Mapped[str] = mapped_column(String(256), index=True)
    title: Mapped[str] = mapped_column(String(512))
    company: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    form_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accounting_standard: Mapped[str | None] = mapped_column(String(64), nullable=True)
    canonical_section: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )


class ChatFeedbackRecord(Base):
    __tablename__ = "chat_feedback"

    feedback_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
    )
    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="CASCADE"),
        index=True,
    )
    rating: Mapped[str] = mapped_column(String(8), index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )