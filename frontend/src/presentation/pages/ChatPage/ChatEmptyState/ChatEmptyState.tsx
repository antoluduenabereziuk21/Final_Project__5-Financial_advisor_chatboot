import type { ChatEmptyStateProps } from "./ChatEmptyStateConfig"

function ChatEmptyState({ message }: ChatEmptyStateProps) {
  return (
    <p className="text-center text-sm text-muted-foreground">{message}</p>
  )
}

export { ChatEmptyState }
