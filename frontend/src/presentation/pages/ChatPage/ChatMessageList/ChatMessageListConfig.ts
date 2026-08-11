import type { RefObject } from "react"

import type { IChatMessage } from "@/domain/entities/ChatMessage"

export interface ChatMessageListProps {
  messages: IChatMessage[]
  isSending: boolean
  error: string | null
  messagesEndRef: RefObject<HTMLDivElement | null>
}

export const chatMessageListCopies = {
  emptyState: "Ask a question about NASDAQ-listed companies to get started.",
  sendingLabel: "Generating response",
  errorTitle: "Unable to send message",
} as const
