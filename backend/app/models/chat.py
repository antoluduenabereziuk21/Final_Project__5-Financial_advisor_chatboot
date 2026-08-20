from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    sessionId: Optional[str] = None
    userId: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    followUp: list[str] = Field(default_factory=list)
    sources: list[dict[str, object]] = Field(default_factory=list)
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None


class ChatFeedbackRequest(BaseModel):
    conversation_id: str
    message_id: str
    rating: Literal["up", "down"]
    reason: Optional[str] = None
    user_id: Optional[str] = None


class ChatFeedback(BaseModel):
    feedback_id: str
    conversation_id: str
    message_id: str
    rating: Literal["up", "down"]
    reason: Optional[str] = None
    user_id: Optional[str] = None
    created_at: str


class ChatFeedbackListResponse(BaseModel):
    items: list[ChatFeedback] = Field(default_factory=list)
    total: int


class SourceDetailResponse(BaseModel):
    chunk_id: str
    title: str
    company: Optional[str] = None
    ticker: Optional[str] = None
    fiscal_year: Optional[int] = None
    form_type: Optional[str] = None
    accounting_standard: Optional[str] = None
    canonical_section: Optional[str] = None
    source_file: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    relevance_score: Optional[float] = None
    text_snippet: Optional[str] = None
    conversation_id: Optional[str] = None


class ConversationSummary(BaseModel):
    conversation_id: str
    user_id: Optional[str] = None
    created_at: str
    updated_at: str


class ConversationListResponse(BaseModel):
    items: list[ConversationSummary] = Field(default_factory=list)
    total: int


class ConversationMessageResponse(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    sources: list[dict[str, object]] = Field(default_factory=list)


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    user_id: Optional[str] = None
    created_at: str
    updated_at: str
    messages: list[ConversationMessageResponse] = Field(default_factory=list)