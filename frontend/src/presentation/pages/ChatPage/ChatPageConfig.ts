import type { RefObject } from "react"

import type { IChatMessage } from "@/domain/entities/ChatMessage"
import type { ChatFeedbackRating } from "@/domain/entities/SubmitFeedbackInput"
import type { ChatMessageFeedbackStatus } from "./ChatMessageFeedback"

export interface ChatPageProps {
  messages: IChatMessage[]
  conversationId: string | null
  feedbackByMessageId: Record<string, ChatMessageFeedbackStatus>
  isSending: boolean
  error: string | null
  messagesEndRef: RefObject<HTMLDivElement | null>
  onSend: (content: string) => boolean | Promise<boolean>
  onCancel: () => void
  onFeedback: (messageId: string, rating: ChatFeedbackRating) => void | Promise<void>
}

export const chatPageCopies = {
  title: "Financial Research Assistant",
} as const
