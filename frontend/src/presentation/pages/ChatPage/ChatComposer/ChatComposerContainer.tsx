import { useState } from "react"

import { ChatComposer } from "./ChatComposer"
import type { ChatComposerContainerProps } from "./ChatComposerConfig"

function ChatComposerContainer({
  isSending,
  onSend,
}: ChatComposerContainerProps) {
  const [value, setValue] = useState("")

  async function handleSend() {
    const trimmed = value.trim()

    if (!trimmed || isSending) {
      return
    }

    setValue("")
    await onSend(trimmed)
  }

  return (
    <ChatComposer
      value={value}
      isSending={isSending}
      onValueChange={setValue}
      onSend={() => {
        void handleSend()
      }}
    />
  )
}

export { ChatComposerContainer }
