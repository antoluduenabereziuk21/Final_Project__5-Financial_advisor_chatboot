from fastapi import APIRouter, HTTPException, Query, Request, status

from app.models.chat import (
    ChatFeedback,
    ChatFeedbackListResponse,
    ChatFeedbackRequest,
    ChatRequest,
    ChatResponse,
    SourceDetailResponse,
)

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


@router.post(
    "/chat/feedback",
    response_model=ChatFeedback,
    status_code=status.HTTP_201_CREATED,
)
async def save_chat_feedback(
    request: ChatFeedbackRequest, fastapi_request: Request
) -> ChatFeedback:
    chat_service = fastapi_request.app.state.chat_service
    feedback = chat_service.save_feedback(
        conversation_id=request.conversation_id,
        message_id=request.message_id,
        rating=request.rating,
        reason=request.reason,
        user_id=request.user_id,
    )
    return ChatFeedback(**feedback)


@router.get("/chat/feedback", response_model=ChatFeedbackListResponse)
async def list_chat_feedback(
    fastapi_request: Request,
    conversation_id: str = Query(..., min_length=1),
) -> ChatFeedbackListResponse:
    chat_service = fastapi_request.app.state.chat_service
    items = chat_service.list_feedback(conversation_id=conversation_id)
    return ChatFeedbackListResponse(items=[ChatFeedback(**item) for item in items], total=len(items))


@router.get("/sources/{chunk_id}", response_model=SourceDetailResponse)
async def get_source_detail(chunk_id: str, fastapi_request: Request) -> SourceDetailResponse:
    chat_service = fastapi_request.app.state.chat_service
    source = chat_service.get_source_detail(chunk_id=chunk_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    return SourceDetailResponse(**source)
