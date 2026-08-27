import type { ISendMessageResult } from "@/domain/entities/SendMessageResult"
import type { ISubmitFeedbackInput } from "@/domain/entities/SubmitFeedbackInput"

export interface IChatRepository {
  sendMessage(
    content: string,
    conversationId?: string | null,
    signal?: AbortSignal,
  ): Promise<ISendMessageResult>
  submitFeedback(input: ISubmitFeedbackInput): Promise<void>
}
