export interface ChatQuestionHistoryItem {
  id: string
  content: string
}

export interface ChatQuestionHistoryProps {
  items: ChatQuestionHistoryItem[]
  isOpen: boolean
  selectedId: string | null
  onOpenChange: (isOpen: boolean) => void
  onSelect: (messageId: string) => void
}

export const chatQuestionHistoryCopies = {
  regionLabel: "Question history",
  selectQuestionLabel: "Go to question",
  emptyLabel: "No questions yet",
} as const
