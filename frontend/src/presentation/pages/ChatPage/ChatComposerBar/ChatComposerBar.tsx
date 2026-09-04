import { ChatComposer } from "../ChatComposer"

import type { ChatComposerBarProps } from "./ChatComposerBarConfig"

function ChatComposerBar({ isSending, onSend, onCancel }: ChatComposerBarProps) {
  return (
    <div className="shrink-0 border-t border-border bg-background px-6 py-4">
      <div className="mx-auto w-full max-w-3xl">
        <ChatComposer
          isSending={isSending}
          onSend={onSend}
          onCancel={onCancel}
        />
      </div>
    </div>
  )
}

export { ChatComposerBar }
