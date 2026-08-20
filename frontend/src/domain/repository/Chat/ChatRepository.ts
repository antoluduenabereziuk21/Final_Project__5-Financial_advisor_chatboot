import type { ISendMessageResult } from "@/domain/entities/SendMessageResult"

export interface IChatRepository {
  sendMessage(
    content: string,
    conversationId?: string | null,
  ): Promise<ISendMessageResult>
}
