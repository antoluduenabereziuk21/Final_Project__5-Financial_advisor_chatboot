from __future__ import annotations

from typing import Protocol

from app.rag.types import RAGContext


class PromptBuilder(Protocol):
    def build_prompt(self, context: RAGContext) -> str:
        ...


class MockPromptBuilder:
    def build_prompt(self, context: RAGContext) -> str:
        # This is the seam for LangChain prompt templates in production.
        history_text = "\n".join(
            f"{message['role']}: {message['content']}" for message in context.conversation_history[-6:]
        )
        document_text = "\n\n".join(
            f"{document.metadata.get('title', document.id)}\n{document.content}"
            for document in context.retrieved_documents
        )

        return (
            "Eres un asistente financiero. Responde usando solo el contexto recuperado.\n\n"
            f"Pregunta:\n{context.question}\n\n"
            f"Historial de conversación:\n{history_text or 'No previous history'}\n\n"
            f"Documentos relevantes:\n{document_text or 'No retrieved documents'}"
        )