import { ChatEmptyState } from "./ChatEmptyState"
import type { ChatEmptyStateProps } from "./ChatEmptyStateConfig"

function ChatEmptyStateContainer(props: ChatEmptyStateProps) {
  return <ChatEmptyState {...props} />
}

export { ChatEmptyStateContainer }
