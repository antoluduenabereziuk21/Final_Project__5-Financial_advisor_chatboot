import type { RefObject } from "react"

import type { IChatMessage } from "@/domain/entities/ChatMessage"

export interface ChatPageProps {
  messages: IChatMessage[]
  searches: string[]
  isSending: boolean
  error: string | null
  messagesEndRef: RefObject<HTMLDivElement | null>
  onSend: (content: string) => void | Promise<void>
  onNewChat: () => void
}

export const chatPageCopies = {
  title: "Financial Research Assistant",
} as const
