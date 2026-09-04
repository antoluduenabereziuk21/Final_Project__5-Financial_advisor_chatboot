export type ChatMessageRole = "user" | "assistant"

export interface IChatMessage {
  id: string
  role: ChatMessageRole
  content: string
  createdAt: string
}
