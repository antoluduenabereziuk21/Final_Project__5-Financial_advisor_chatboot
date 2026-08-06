from fastapi import APIRouter

from app.models.chat import ChatRequest, ChatResponse
from app.models.welcome import WelcomeContent

api_router = APIRouter(tags=["api"])


@api_router.get("/welcome", response_model=WelcomeContent)
async def get_welcome_content() -> WelcomeContent:
    return WelcomeContent(
        title="Financial Advisor",
        description="Get clear, practical guidance for your money decisions in a focused chat.",
        ctaLabel="Start conversation",
    )


@api_router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    user_message = payload.message.strip()

    if not user_message:
        return ChatResponse(
            answer="Please share your question so I can help you with a financial decision.",
            followUp=[
                "What is your current goal?",
                "Do you have a monthly budget target?",
            ],
        )

    return ChatResponse(
        answer=(
            "Thanks for your message. This is the base backend response. "
            "Next, we can connect this endpoint with your RAG and LLM pipeline."
        ),
        followUp=[
            "Do you want short-term or long-term advice?",
            "What is your risk tolerance (low, medium, high)?",
        ],
    )