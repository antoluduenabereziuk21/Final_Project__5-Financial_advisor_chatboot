import { ChatComposerAttachButton } from "../ChatComposerAttachButton"
import { ChatComposerDisclaimer } from "../ChatComposerDisclaimer"
import { ChatComposerInput } from "../ChatComposerInput"
import { ChatComposerSendButton } from "../ChatComposerSendButton"

import { chatComposerCopies, type ChatComposerProps } from "./ChatComposerConfig"

function ChatComposer({
  value,
  isSending,
  onValueChange,
  onSend,
  onCancel,
  onAttach,
}: ChatComposerProps) {
  const canSubmit = value.trim().length > 0 && !isSending

  return (
    <div className="flex w-full flex-col gap-3">
      <div className="flex items-end gap-2 rounded-4xl border border-border bg-card px-3 py-2 shadow-sm">
        <ChatComposerAttachButton onAttach={onAttach} />
        <ChatComposerInput
          id={chatComposerCopies.inputId}
          value={value}
          placeholder={chatComposerCopies.placeholder}
          disabled={isSending}
          canSubmit={canSubmit}
          onValueChange={onValueChange}
          onSubmit={onSend}
        />
        <ChatComposerSendButton
          isSending={isSending}
          disabled={!canSubmit}
          onSend={onSend}
          onCancel={onCancel}
        />
      </div>
      <ChatComposerDisclaimer text={chatComposerCopies.disclaimer} />
    </div>
  )
}

export { ChatComposer }
