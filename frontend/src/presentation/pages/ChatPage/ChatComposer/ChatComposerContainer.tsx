import { useState } from "react"

import { ChatComposer } from "./ChatComposer"
import type { ChatComposerContainerProps } from "./ChatComposerConfig"

function ChatComposerContainer({
  isSending,
  onSend,
  onCancel,
}: ChatComposerContainerProps) {
  const [value, setValue] = useState("")

  async function handleSend() {
    const trimmed = value.trim()

    if (!trimmed || isSending) {
      return
    }

    const sent = await onSend(trimmed)

    if (sent) {
      setValue("")
    }
  }

  return (
    <ChatComposer
      value={value}
      isSending={isSending}
      onValueChange={setValue}
      onSend={() => {
        void handleSend()
      }}
      onCancel={onCancel}
    />
  )
}

export { ChatComposerContainer }
