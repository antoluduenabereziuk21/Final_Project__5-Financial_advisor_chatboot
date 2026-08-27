import type { RefObject } from "react"

import type { IChatMessage } from "@/domain/entities/ChatMessage"
import type { ChatFeedbackRating } from "@/domain/entities/SubmitFeedbackInput"
import type { ChatMessageFeedbackStatus } from "../ChatMessageFeedback/ChatMessageFeedbackConfig"

export interface ChatMessageListProps {
  messages: IChatMessage[]
  conversationId: string | null
  feedbackByMessageId: Record<string, ChatMessageFeedbackStatus>
  isSending: boolean
  error: string | null
  messagesEndRef: RefObject<HTMLDivElement | null>
  onFeedback: (messageId: string, rating: ChatFeedbackRating) => void | Promise<void>
}

export const chatMessageListCopies = {
  emptyState: "Ask a question about NASDAQ-listed companies to get started.",
  sendingLabel: "Generating response",
  errorTitle: "Unable to send message",
} as const
