import { ThumbsDownIcon, ThumbsUpIcon } from "lucide-react"

import { IconButton } from "@/presentation/components/IconButton"

import {
  chatMessageFeedbackCopies,
  type ChatMessageFeedbackProps,
} from "./ChatMessageFeedbackConfig"

function ChatMessageFeedback({ status, onRate }: ChatMessageFeedbackProps) {
  const isPending = status === "pending"
  const hasVoted = status === "up" || status === "down"
  const isDisabled = isPending || hasVoted

  return (
    <div className="mt-2 flex items-center gap-1">
      <IconButton
        variant={status === "up" ? "secondary" : "ghost"}
        size="icon-xs"
        ariaLabel={chatMessageFeedbackCopies.thumbsUpLabel}
        disabled={isDisabled}
        onClick={() => onRate("up")}
      >
        <ThumbsUpIcon aria-hidden="true" />
      </IconButton>
      <IconButton
        variant={status === "down" ? "secondary" : "ghost"}
        size="icon-xs"
        ariaLabel={chatMessageFeedbackCopies.thumbsDownLabel}
        disabled={isDisabled}
        onClick={() => onRate("down")}
      >
        <ThumbsDownIcon aria-hidden="true" />
      </IconButton>
      {status === "error" ? (
        <span className="text-xs text-destructive">
          {chatMessageFeedbackCopies.errorLabel}
        </span>
      ) : null}
    </div>
  )
}

export { ChatMessageFeedback }
