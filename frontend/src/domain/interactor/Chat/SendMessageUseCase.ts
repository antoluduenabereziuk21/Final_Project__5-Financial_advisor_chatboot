import { decorate, inject, injectable } from "inversify"

import { RepositoryTypes } from "@/domain/entities/structure/RepositoryTypes"
import type { ISendMessageResult } from "@/domain/entities/SendMessageResult"
import type { IChatRepository } from "@/domain/repository/Chat/ChatRepository"

@injectable()
export default class SendMessageUseCase {
  private readonly chatRepository!: IChatRepository

  async execute(content: string): Promise<ISendMessageResult> {
    const trimmed = content.trim()

    if (!trimmed) {
      throw new Error("Message content cannot be empty.")
    }

    return this.chatRepository.sendMessage(trimmed)
  }
}

decorate(
  inject(RepositoryTypes.ChatRepository) as PropertyDecorator,
  SendMessageUseCase,
  "chatRepository",
)
