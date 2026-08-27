import type { IChatSource } from "@/domain/entities/ChatSource"

export type ChatMessageRole = "user" | "assistant"

export interface IChatMessage {
  id: string
  role: ChatMessageRole
  content: string
  createdAt: string
  sources?: IChatSource[]
}
