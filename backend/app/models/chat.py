from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None
    userId: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    followUp: list[str] = Field(default_factory=list)