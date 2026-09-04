import { ChatSendingStatus } from "./ChatSendingStatus"
import type { ChatSendingStatusProps } from "./ChatSendingStatusConfig"

function ChatSendingStatusContainer(props: ChatSendingStatusProps) {
  return <ChatSendingStatus {...props} />
}

export { ChatSendingStatusContainer }
