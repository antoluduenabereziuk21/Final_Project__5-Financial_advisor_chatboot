from fastapi import APIRouter

from app.models.welcome import WelcomeContent

api_router = APIRouter(tags=["api"])


@api_router.get("/welcome", response_model=WelcomeContent)
async def get_welcome_content() -> WelcomeContent:
    return WelcomeContent(
        title="Financial Advisor",
        description="Get clear, practical guidance for your money decisions in a focused chat.",
        ctaLabel="Start conversation",
    )