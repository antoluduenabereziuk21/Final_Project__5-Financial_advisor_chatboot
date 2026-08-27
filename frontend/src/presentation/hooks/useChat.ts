import { useRef, useState } from "react"

import { HttpError } from "@/data/errors/HttpError"
import type { IChatMessage } from "@/domain/entities/ChatMessage"
import type { ChatFeedbackRating } from "@/domain/entities/SubmitFeedbackInput"
import { UseCaseTypes } from "@/domain/entities/structure/UseCaseTypes"
import type SendMessageUseCase from "@/domain/interactor/Chat/SendMessageUseCase"
import type SubmitFeedbackUseCase from "@/domain/interactor/Chat/SubmitFeedbackUseCase"
import { container } from "@/presentation/config/inversify.config"
import type { ChatMessageFeedbackStatus } from "@/presentation/pages/ChatPage/ChatMessageFeedback/ChatMessageFeedbackConfig"

const useChatCopies = {
  sendError: "Unable to send your message. Please try again.",
} as const

function isRequestCancelled(error: unknown): boolean {
  return error instanceof HttpError && error.code === "REQUEST_CANCELLED"
}

export function useChat() {
  const [messages, setMessages] = useState<IChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [feedbackByMessageId, setFeedbackByMessageId] = useState<
    Record<string, ChatMessageFeedbackStatus>
  >({})
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  async function sendMessage(content: string): Promise<boolean> {
    abortControllerRef.current?.abort()
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    setIsSending(true)
    setError(null)

    try {
      const useCase = container.get<SendMessageUseCase>(
        UseCaseTypes.SendMessageUseCase,
      )
      const result = await useCase.execute(
        content,
        conversationId,
        abortController.signal,
      )

      if (result.conversationId) {
        setConversationId(result.conversationId)
      }

      setMessages((previous) => [
        ...previous,
        result.userMessage,
        result.assistantMessage,
      ])
      return true
    } catch (caughtError) {
      if (isRequestCancelled(caughtError)) {
        return false
      }

      setError(useChatCopies.sendError)
      return false
    } finally {
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null
      }
      setIsSending(false)
    }
  }

  function cancelMessage() {
    abortControllerRef.current?.abort()
  }

  async function submitFeedback(messageId: string, rating: ChatFeedbackRating) {
    if (!conversationId) {
      return
    }

    setFeedbackByMessageId((previous) => ({
      ...previous,
      [messageId]: "pending",
    }))

    try {
      const useCase = container.get<SubmitFeedbackUseCase>(
        UseCaseTypes.SubmitFeedbackUseCase,
      )
      await useCase.execute({
        conversationId,
        messageId,
        rating,
      })

      setFeedbackByMessageId((previous) => ({
        ...previous,
        [messageId]: rating,
      }))
    } catch {
      setFeedbackByMessageId((previous) => ({
        ...previous,
        [messageId]: "error",
      }))
    }
  }

  return {
    messages,
    conversationId,
    feedbackByMessageId,
    isSending,
    error,
    sendMessage,
    cancelMessage,
    submitFeedback,
  }
}
