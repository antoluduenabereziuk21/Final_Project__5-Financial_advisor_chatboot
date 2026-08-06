import { Send } from "lucide-react"

import { IconButton } from "@/presentation/components/IconButton"

import {
  chatComposerSendButtonCopies,
  type ChatComposerSendButtonProps,
} from "./ChatComposerSendButtonConfig"

function ChatComposerSendButton({
  disabled,
  onSend,
}: ChatComposerSendButtonProps) {
  return (
    <IconButton
      type="button"
      variant="default"
      size="icon"
      ariaLabel={chatComposerSendButtonCopies.ariaLabel}
      disabled={disabled}
      onClick={onSend}
    >
      <Send />
    </IconButton>
  )
}

export { ChatComposerSendButton }
