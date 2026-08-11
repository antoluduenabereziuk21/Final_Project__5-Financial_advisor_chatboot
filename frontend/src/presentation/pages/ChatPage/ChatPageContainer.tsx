import { useEffect, useRef } from "react"

import { useChat } from "@/presentation/hooks/useChat"

import { ChatPage } from "./ChatPage"

function ChatPageContainer() {
  const { messages, searches, isSending, error, sendMessage, resetChat } = useChat()
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
      searches={searches}
      isSending={isSending}
      error={error}
      messagesEndRef={messagesEndRef}
      onSend={sendMessage}
      onNewChat={resetChat}
    />
  )
}

export { ChatPageContainer }
