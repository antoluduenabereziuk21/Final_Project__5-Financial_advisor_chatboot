import type { ChatMessageRole } from "@/domain/entities/ChatMessage"

export interface ChatMessageBubbleProps {
  role: ChatMessageRole
  content: string
}

export const chatMessageBubbleCopies = {
  userMessageLabel: "Your message",
  assistantMessageLabel: "Assistant message",
} as const
