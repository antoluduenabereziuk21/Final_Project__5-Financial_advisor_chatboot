import { Spinner } from "@/presentation/components/Spinner"

import type { ChatSendingStatusProps } from "./ChatSendingStatusConfig"

function ChatSendingStatus({ label }: ChatSendingStatusProps) {
  return (
    <div
      className="flex items-center gap-3 text-muted-foreground"
      role="status"
      aria-label={label}
    >
      <Spinner />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export { ChatSendingStatus }
