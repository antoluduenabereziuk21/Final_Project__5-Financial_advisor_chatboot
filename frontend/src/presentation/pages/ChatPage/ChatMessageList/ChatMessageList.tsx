import { ChatEmptyState } from "../ChatEmptyState"
import { ChatError } from "../ChatError"
import { ChatMessageBubble } from "../ChatMessageBubble"
import { ChatSendingStatus } from "../ChatSendingStatus"
import { ScrollArea } from "@/presentation/components/ScrollArea"

import {
  chatMessageListCopies,
  type ChatMessageListProps,
} from "./ChatMessageListConfig"

function ChatMessageList({
  messages,
  isSending,
  error,
  messagesEndRef,
}: ChatMessageListProps) {
  const showEmptyState = messages.length === 0 && !isSending

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-8">
        {showEmptyState ? (
          <ChatEmptyState message={chatMessageListCopies.emptyState} />
        ) : null}

        {messages.map((message) => (
          <ChatMessageBubble
            key={message.id}
            role={message.role}
            content={message.content}
          />
        ))}

        {isSending ? (
          <ChatSendingStatus label={chatMessageListCopies.sendingLabel} />
        ) : null}

        {error ? (
          <ChatError
            title={chatMessageListCopies.errorTitle}
            message={error}
          />
        ) : null}

        <div ref={messagesEndRef} />
      </div>
    </ScrollArea>
  )
}

export { ChatMessageList }
