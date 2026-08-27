import type { ChatFeedbackRating } from "@/domain/entities/SubmitFeedbackInput"

export type ChatMessageFeedbackStatus =
  | "idle"
  | "pending"
  | "up"
  | "down"
  | "error"

export interface ChatMessageFeedbackProps {
  status: ChatMessageFeedbackStatus
  onRate: (rating: ChatFeedbackRating) => void
}

export const chatMessageFeedbackCopies = {
  thumbsUpLabel: "Mark response as helpful",
  thumbsDownLabel: "Mark response as not helpful",
  errorLabel: "Could not save feedback",
} as const
