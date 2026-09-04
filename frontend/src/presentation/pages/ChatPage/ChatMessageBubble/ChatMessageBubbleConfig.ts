import type { IChatSource } from "@/domain/entities/ChatSource"
import type { ChatMessageRole } from "@/domain/entities/ChatMessage"
import type { ChatFeedbackRating } from "@/domain/entities/SubmitFeedbackInput"
import type { ChatMessageFeedbackStatus } from "../ChatMessageFeedback/ChatMessageFeedbackConfig"

export interface ChatMessageBubbleProps {
  id: string
  role: ChatMessageRole
  content: string
  createdAt: string
  sources?: IChatSource[]
  conversationId?: string | null
  feedbackStatus?: ChatMessageFeedbackStatus
  onFeedback?: (rating: ChatFeedbackRating) => void
}

export const chatMessageBubbleCopies = {
  userMessageLabel: "Your message",
  assistantMessageLabel: "Assistant message",
} as const
