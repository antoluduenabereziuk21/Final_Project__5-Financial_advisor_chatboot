import { useState } from "react"

import type { IChatMessage } from "@/domain/entities/ChatMessage"

import { ChatQuestionHistory } from "./ChatQuestionHistory"
import type { ChatQuestionHistoryItem } from "./ChatQuestionHistoryConfig"

export interface ChatQuestionHistoryContainerProps {
  messages: IChatMessage[]
}

function ChatQuestionHistoryContainer({
  messages,
}: ChatQuestionHistoryContainerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const items: ChatQuestionHistoryItem[] = messages
    .filter((message) => message.role === "user")
    .map((message) => ({
      id: message.id,
      content: message.content,
    }))

  function handleSelect(messageId: string) {
    const target = document.getElementById(`chat-message-${messageId}`)

    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" })
    }

    setSelectedId(messageId)
  }

  return (
    <ChatQuestionHistory
      items={items}
      isOpen={isOpen}
      selectedId={selectedId}
      onOpenChange={setIsOpen}
      onSelect={handleSelect}
    />
  )
}

export { ChatQuestionHistoryContainer }
