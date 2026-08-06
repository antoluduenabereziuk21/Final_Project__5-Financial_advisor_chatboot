import { useEffect, useRef } from "react"

import { useChat } from "@/presentation/hooks/useChat"

import { ChatPage } from "./ChatPage"

function ChatPageContainer() {
  const { messages, isSending, error, sendMessage } = useChat()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const endNode = messagesEndRef.current

    if (!endNode) {
      return
    }

    endNode.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages, isSending, error])

  return (
    <ChatPage
      messages={messages}
      isSending={isSending}
      error={error}
      messagesEndRef={messagesEndRef}
      onSend={sendMessage}
    />
  )
}

export { ChatPageContainer }
