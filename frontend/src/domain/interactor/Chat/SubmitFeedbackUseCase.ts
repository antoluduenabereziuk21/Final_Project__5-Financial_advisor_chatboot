import { decorate, inject, injectable } from "inversify"

import { RepositoryTypes } from "@/domain/entities/structure/RepositoryTypes"
import type { ISubmitFeedbackInput } from "@/domain/entities/SubmitFeedbackInput"
import type { IChatRepository } from "@/domain/repository/Chat/ChatRepository"

@injectable()
export default class SubmitFeedbackUseCase {
  private readonly chatRepository!: IChatRepository

  async execute(input: ISubmitFeedbackInput): Promise<void> {
    const conversationId = input.conversationId.trim()
    const messageId = input.messageId.trim()

    if (!conversationId || !messageId) {
      throw new Error("Conversation id and message id are required.")
    }

    if (input.rating !== "up" && input.rating !== "down") {
      throw new Error("Feedback rating must be up or down.")
    }

    await this.chatRepository.submitFeedback({
      conversationId,
      messageId,
      rating: input.rating,
    })
  }
}

decorate(
  inject(RepositoryTypes.ChatRepository) as PropertyDecorator,
  SubmitFeedbackUseCase,
  "chatRepository",
)
