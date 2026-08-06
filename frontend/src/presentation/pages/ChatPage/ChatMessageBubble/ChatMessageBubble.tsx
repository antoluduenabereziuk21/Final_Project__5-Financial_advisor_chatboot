import { cn } from "@/lib/utils"

import {
  chatMessageBubbleCopies,
  type ChatMessageBubbleProps,
} from "./ChatMessageBubbleConfig"

function ChatMessageBubble({ role, content }: ChatMessageBubbleProps) {
  const isUser = role === "user"

  return (
    <div
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div
        role="article"
        aria-label={
          isUser
            ? chatMessageBubbleCopies.userMessageLabel
            : chatMessageBubbleCopies.assistantMessageLabel
        }
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap",
          isUser
            ? "bg-primary text-primary-foreground"
            : "border border-border bg-card text-card-foreground",
        )}
      >
        {content}
      </div>
    </div>
  )
}

export { ChatMessageBubble }
