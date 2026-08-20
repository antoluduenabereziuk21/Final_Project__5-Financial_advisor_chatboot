from fastapi import APIRouter, HTTPException, Query, Request, status

from app.models.chat import (
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationSummary,
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
    feedback = await chat_service.save_feedback(
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
    items = await chat_service.list_feedback(conversation_id=conversation_id)
    return ChatFeedbackListResponse(items=[ChatFeedback(**item) for item in items], total=len(items))


@router.get("/chat/conversations", response_model=ConversationListResponse)
async def list_conversations(
    fastapi_request: Request,
    limit: int = Query(20, ge=1, le=100),
) -> ConversationListResponse:
    chat_service = fastapi_request.app.state.chat_service
    items = await chat_service.list_conversations(limit=limit)
    return ConversationListResponse(
        items=[ConversationSummary(**item) for item in items],
        total=len(items),
    )


@router.get(
    "/chat/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
async def get_conversation_detail(
    conversation_id: str,
    fastapi_request: Request,
) -> ConversationDetailResponse:
    chat_service = fastapi_request.app.state.chat_service
    detail = await chat_service.get_conversation_detail(conversation_id=conversation_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return ConversationDetailResponse(
        conversation_id=str(detail["conversation_id"]),
        user_id=detail.get("user_id"),
        created_at=str(detail["created_at"]),
        updated_at=str(detail["updated_at"]),
        messages=[ConversationMessageResponse(**message) for message in detail["messages"]],
    )


@router.get("/sources/{chunk_id}", response_model=SourceDetailResponse)
async def get_source_detail(chunk_id: str, fastapi_request: Request) -> SourceDetailResponse:
    chat_service = fastapi_request.app.state.chat_service
    source = await chat_service.get_source_detail(chunk_id=chunk_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    return SourceDetailResponse(**source)
