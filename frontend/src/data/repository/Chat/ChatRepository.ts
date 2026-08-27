import { injectable } from "inversify"

import httpClient from "@/data/provider/httpClient"
import type { IChatSource } from "@/domain/entities/ChatSource"
import type { ISendMessageResult } from "@/domain/entities/SendMessageResult"
import type { ISubmitFeedbackInput } from "@/domain/entities/SubmitFeedbackInput"
import type { IChatRepository } from "@/domain/repository/Chat/ChatRepository"

interface ChatSourceApiItem {
  chunk_id?: string | null
  title?: string | null
  company?: string | null
  ticker?: string | null
  fiscal_year?: number | null
  form_type?: string | null
  page_start?: number | null
  page_end?: number | null
  text_snippet?: string | null
  content?: string | null
  relevance_score?: number | null
  source_file?: string | null
}

interface ChatApiResponse {
  answer: string
  followUp: string[]
  sources: ChatSourceApiItem[]
  conversation_id: string | null
  message_id: string | null
}

function createId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
}

function asString(value: unknown): string | null {
  if (typeof value === "string" && value.trim().length > 0) {
    return value
  }

  return null
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function mapSource(item: ChatSourceApiItem, index: number): IChatSource {
  const chunkId = asString(item.chunk_id) ?? `source-${index}`
  const title =
    asString(item.title) ??
    asString(item.source_file) ??
    asString(item.company) ??
    chunkId

  return {
    chunkId,
    title,
    company: asString(item.company),
    ticker: asString(item.ticker),
    fiscalYear: asNumber(item.fiscal_year),
    formType: asString(item.form_type),
    pageStart: asNumber(item.page_start),
    pageEnd: asNumber(item.page_end),
    textSnippet: asString(item.text_snippet) ?? asString(item.content),
    relevanceScore: asNumber(item.relevance_score),
  }
}

@injectable()
export default class ChatRepository implements IChatRepository {
  async sendMessage(
    content: string,
    conversationId?: string | null,
    signal?: AbortSignal,
  ): Promise<ISendMessageResult> {
    const createdAt = new Date().toISOString()

    const response = await httpClient.post<ChatApiResponse>(
      "/api/chat",
      {
        message: content,
        ...(conversationId ? { conversation_id: conversationId } : {}),
      },
      { signal },
    )

    const data = response.data
    const sources = Array.isArray(data.sources)
      ? data.sources.map(mapSource)
      : []

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
        sources,
      },
      conversationId: data.conversation_id ?? conversationId ?? null,
    }
  }

  async submitFeedback(input: ISubmitFeedbackInput): Promise<void> {
    await httpClient.post("/api/chat/feedback", {
      conversation_id: input.conversationId,
      message_id: input.messageId,
      rating: input.rating,
    })
  }
}
