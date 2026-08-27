import { cn } from "@/lib/utils"

import { ChatMessageFeedback } from "../ChatMessageFeedback"
import { ChatMessageMarkdown } from "../ChatMessageMarkdown"
import { ChatMessageSources } from "../ChatMessageSources"

import {
  chatMessageBubbleCopies,
  type ChatMessageBubbleProps,
} from "./ChatMessageBubbleConfig"

function formatMessageTime(createdAt: string): string {
  const date = new Date(createdAt)

  if (Number.isNaN(date.getTime())) {
    return ""
  }

  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(date)
}

function ChatMessageBubble({
  id,
  role,
  content,
  createdAt,
  sources,
  conversationId,
  feedbackStatus = "idle",
  onFeedback,
}: ChatMessageBubbleProps) {
  const isUser = role === "user"
  const timeLabel = formatMessageTime(createdAt)
  const showSources = !isUser && Boolean(sources && sources.length > 0)
  const showFeedback =
    !isUser && Boolean(conversationId) && typeof onFeedback === "function"

  return (
    <div
      id={`chat-message-${id}`}
      className={cn(
        "flex w-full scroll-mt-24",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={cn(
          "flex max-w-[85%] flex-col",
          isUser ? "items-end" : "items-start",
        )}
      >
        <div
          role="article"
          aria-label={
            isUser
              ? chatMessageBubbleCopies.userMessageLabel
              : chatMessageBubbleCopies.assistantMessageLabel
          }
          className={cn(
            "rounded-2xl px-4 py-3 text-sm",
            isUser
              ? "bg-primary text-primary-foreground whitespace-pre-wrap"
              : "border border-border bg-card text-card-foreground",
          )}
        >
          {isUser ? content : <ChatMessageMarkdown content={content} />}
          {showSources && sources ? (
            <ChatMessageSources sources={sources} />
          ) : null}
        </div>
        {timeLabel ? (
          <span className="mt-1 px-1 text-xs text-muted-foreground">
            {timeLabel}
          </span>
        ) : null}
        {showFeedback && onFeedback ? (
          <ChatMessageFeedback status={feedbackStatus} onRate={onFeedback} />
        ) : null}
      </div>
    </div>
  )
}

export { ChatMessageBubble }
