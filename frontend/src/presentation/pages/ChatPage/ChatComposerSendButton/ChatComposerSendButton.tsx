import { SendIcon, SquareIcon } from "lucide-react"

import { IconButton } from "@/presentation/components/IconButton"

import {
  chatComposerSendButtonCopies,
  type ChatComposerSendButtonProps,
} from "./ChatComposerSendButtonConfig"

function ChatComposerSendButton({
  isSending,
  disabled,
  onSend,
  onCancel,
}: ChatComposerSendButtonProps) {
  if (isSending) {
    return (
      <IconButton
        type="button"
        variant="default"
        size="icon"
        ariaLabel={chatComposerSendButtonCopies.cancelAriaLabel}
        onClick={onCancel}
      >
        <SquareIcon className="size-3.5 fill-current" aria-hidden="true" />
      </IconButton>
    )
  }

  return (
    <IconButton
      type="button"
      variant="default"
      size="icon"
      ariaLabel={chatComposerSendButtonCopies.sendAriaLabel}
      disabled={disabled}
      onClick={onSend}
    >
      <SendIcon aria-hidden="true" />
    </IconButton>
  )
}

export { ChatComposerSendButton }
