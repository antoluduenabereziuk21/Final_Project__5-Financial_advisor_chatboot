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
  conversationId,
  feedbackByMessageId,
  isSending,
  error,
  messagesEndRef,
  onFeedback,
}: ChatMessageListProps) {
  const showEmptyState = messages.length === 0 && !isSending

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-8">
        {showEmptyState ? (
          <ChatEmptyState message={chatMessageListCopies.emptyState} />
        ) : null}

        {messages.map((message) => (
          <ChatMessageBubble
            key={message.id}
            id={message.id}
            role={message.role}
            content={message.content}
            createdAt={message.createdAt}
            sources={message.sources}
            conversationId={
              message.role === "assistant" ? conversationId : null
            }
            feedbackStatus={feedbackByMessageId[message.id] ?? "idle"}
            onFeedback={
              message.role === "assistant"
                ? (rating) => onFeedback(message.id, rating)
                : undefined
            }
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
