export type ChatFeedbackRating = "up" | "down"

export interface ISubmitFeedbackInput {
  conversationId: string
  messageId: string
  rating: ChatFeedbackRating
}
