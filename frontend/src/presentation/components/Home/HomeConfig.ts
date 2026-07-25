export interface HomeProps {
  title: string
  description: string
  ctaLabel: string
  isLoading: boolean
  error: string | null
  onStartConversation: () => void
}

export const homeCopies = {
  brand: "Financial Advisor",
  loadingLabel: "Loading",
  errorFallback: "Something went wrong. Please try again.",
  startConversationAriaLabel: "Start conversation with the financial advisor",
} as const
