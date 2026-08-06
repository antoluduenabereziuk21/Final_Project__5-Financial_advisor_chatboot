from typing import Optional

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