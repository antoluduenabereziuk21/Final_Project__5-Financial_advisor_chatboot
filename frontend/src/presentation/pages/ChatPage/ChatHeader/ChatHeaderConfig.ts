export interface ChatHeaderProps {
  title: string
  searches: string[]
  onNewChat: () => void
}

export const chatHeaderCopies = {
  title: "Financial Research Assistant",
  openMenu: "Open search history",
} as const
