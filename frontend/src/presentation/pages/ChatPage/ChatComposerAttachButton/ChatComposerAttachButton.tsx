import { Paperclip } from "lucide-react"

import { IconButton } from "@/presentation/components/IconButton"

import {
  chatComposerAttachButtonCopies,
  type ChatComposerAttachButtonProps,
} from "./ChatComposerAttachButtonConfig"

function ChatComposerAttachButton({
  disabled = true,
  onAttach,
}: ChatComposerAttachButtonProps) {
  return (
    <IconButton
      type="button"
      variant="ghost"
      size="icon"
      ariaLabel={chatComposerAttachButtonCopies.ariaLabel}
      disabled={disabled}
      onClick={onAttach}
    >
      <Paperclip />
    </IconButton>
  )
}

export { ChatComposerAttachButton }
