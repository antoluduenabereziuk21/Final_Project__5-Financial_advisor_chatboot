from fastapi import APIRouter, Request

from app.models.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, fastapi_request: Request) -> ChatResponse:
    chat_service = fastapi_request.app.state.chat_service
    conversation_id = request.conversation_id or request.sessionId or request.userId
    result = await chat_service.handle_message(
        message=request.message,
        conversation_id=conversation_id,
    )
    return ChatResponse(**result)
