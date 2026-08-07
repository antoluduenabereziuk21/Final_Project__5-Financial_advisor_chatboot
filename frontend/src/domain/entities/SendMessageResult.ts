import type { IChatMessage } from "@/domain/entities/ChatMessage"

export interface ISendMessageResult {
  userMessage: IChatMessage
  assistantMessage: IChatMessage
}
