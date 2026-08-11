import { useState } from "react"

import type { IChatMessage } from "@/domain/entities/ChatMessage"
import { UseCaseTypes } from "@/domain/entities/structure/UseCaseTypes"
import type SendMessageUseCase from "@/domain/interactor/Chat/SendMessageUseCase"
import { container } from "@/presentation/config/inversify.config"

const useChatCopies = {
  sendError: "Unable to send your message. Please try again.",
} as const

export function useChat() {
  const [messages, setMessages] = useState<IChatMessage[]>([])
  const [searches, setSearches] = useState<string[]>([])
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function sendMessage(content: string) {
    setIsSending(true)
    setError(null)

    try {
      const useCase = container.get<SendMessageUseCase>(
        UseCaseTypes.SendMessageUseCase,
      )
      const result = await useCase.execute(content)

      setMessages((previous) => [
        ...previous,
        result.userMessage,
        result.assistantMessage,
      ])
      setSearches((previous) => [content, ...previous])
    } catch {
      setError(useChatCopies.sendError)
    } finally {
      setIsSending(false)
    }
  }

  function resetChat() {
    setMessages([])
    setError(null)
  }

  return {
    messages,
    searches,
    isSending,
    error,
    sendMessage,
    resetChat,
  }
}
