from pydantic import BaseModel


class WelcomeContent(BaseModel):
    title: str
    description: str
    ctaLabel: str