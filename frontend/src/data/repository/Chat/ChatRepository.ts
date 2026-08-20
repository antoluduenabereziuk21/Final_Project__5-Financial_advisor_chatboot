import { injectable } from "inversify"

import httpClient from "@/data/provider/httpClient"
import type { ISendMessageResult } from "@/domain/entities/SendMessageResult"
import type { IChatRepository } from "@/domain/repository/Chat/ChatRepository"

interface ChatApiResponse {
  answer: string
  followUp: string[]
  sources: Record<string, object>[]
  conversation_id: string | null
  message_id: string | null
}

function createId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
}

@injectable()
export default class ChatRepository implements IChatRepository {
  async sendMessage(
    content: string,
    conversationId?: string | null,
  ): Promise<ISendMessageResult> {
    const createdAt = new Date().toISOString()

    const response = await httpClient.post<ChatApiResponse>("/api/chat", {
      message: content,
      conversation_id: conversationId ?? undefined,
    })

    const data = response.data

    return {
      userMessage: {
        id: createId("user"),
        role: "user",
        content,
        createdAt,
      },
      assistantMessage: {
        id: data.message_id ?? createId("assistant"),
        role: "assistant",
        content: data.answer,
        createdAt: new Date().toISOString(),
      },
      conversationId: data.conversation_id ?? conversationId ?? null,
    }
  }
}
