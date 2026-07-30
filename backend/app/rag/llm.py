from __future__ import annotations

from typing import Protocol


class LLMService(Protocol):
    async def generate(self, prompt: str) -> str:
        ...


class MockLLMService:
    async def generate(self, prompt: str) -> str:
        lower_prompt = prompt.lower()

        # This is the seam for ChatOpenAI / other hosted or local LLM providers.
        if "apple" in lower_prompt:
            return (
                "Apple presenta una situación financiera sólida, con liquidez robusta, "
                "capacidad de generación de caja y una base de ingresos diversificada."
            )

        if prompt:
            return "La respuesta se generó a partir del contexto recuperado y el prompt construido."

        return "Todavía no hay un LLM real conectado, pero el flujo RAG quedó listo para integrarlo."
