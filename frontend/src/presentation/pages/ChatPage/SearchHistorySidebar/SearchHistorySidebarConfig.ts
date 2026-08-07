export interface SearchHistorySidebarProps {
  searches: string[]
  onNewChat: () => void
  className?: string
}

export const searchHistorySidebarCopies = {
  brand: "Financial Advisor",
  newChat: "New chat",
  historyTitle: "Search history",
  emptyHistory: "Your searches will appear here.",
} as const
