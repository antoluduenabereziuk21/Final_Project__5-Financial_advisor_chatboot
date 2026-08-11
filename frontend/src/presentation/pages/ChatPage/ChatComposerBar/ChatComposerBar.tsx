import { ChatComposer } from "../ChatComposer"

import type { ChatComposerBarProps } from "./ChatComposerBarConfig"

function ChatComposerBar({ isSending, onSend }: ChatComposerBarProps) {
  return (
    <div className="border-t border-border px-6 py-4">
      <div className="mx-auto w-full max-w-3xl">
        <ChatComposer isSending={isSending} onSend={onSend} />
      </div>
    </div>
  )
}

export { ChatComposerBar }
