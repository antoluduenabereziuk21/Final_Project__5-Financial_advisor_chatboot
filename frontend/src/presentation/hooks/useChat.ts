import { useState } from "react"

import type { IChatMessage } from "@/domain/entities/ChatMessage"
import { UseCaseTypes } from "@/domain/entities/structure/UseCaseTypes"
import type SendMessageUseCase from "@/domain/interactor/Chat/SendMessageUseCase"
import { container } from "@/presentation/config/inversify.config"

const useChatCopies = {
  sendError: "Unable to send your message. Please try again.",
} as const

const conversationStorageKey = "financial-advisor-chat-conversation-id"

function createTemporaryConversationId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }

  return `temp-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`
}

function getStoredConversationId(): string | null {
  if (typeof window === "undefined") {
    return null
  }

  const storedConversationId = window.localStorage.getItem(conversationStorageKey)

  if (storedConversationId) {
    return storedConversationId
  }

  const generatedConversationId = createTemporaryConversationId()
  window.localStorage.setItem(conversationStorageKey, generatedConversationId)

  return generatedConversationId
}

function storeConversationId(conversationId: string | null) {
  if (typeof window === "undefined" || !conversationId) {
    return
  }

  window.localStorage.setItem(conversationStorageKey, conversationId)
}

export function useChat() {
  const [messages, setMessages] = useState<IChatMessage[]>([])
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(() =>
    getStoredConversationId(),
  )

  async function sendMessage(content: string) {
    setIsSending(true)
    setError(null)

    try {
      const useCase = container.get<SendMessageUseCase>(
        UseCaseTypes.SendMessageUseCase,
      )
      const result = await useCase.execute(content, conversationId)

      storeConversationId(result.conversationId)
      setConversationId(result.conversationId)

      setMessages((previous) => [
        ...previous,
        result.userMessage,
        result.assistantMessage,
      ])
    } catch {
      setError(useChatCopies.sendError)
    } finally {
      setIsSending(false)
    }
  }

  return {
    messages,
    isSending,
    error,
    sendMessage,
  }
}
