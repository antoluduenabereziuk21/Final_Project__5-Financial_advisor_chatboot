import { injectable } from "inversify"

import { mapSendMessageDTOToSendMessageResult } from "@/data/adapters/mapSendMessageDTOToSendMessageResult"
import type { ISendMessageResponseDTO } from "@/data/entities/SendMessageDTO"
import type { ISendMessageResult } from "@/domain/entities/SendMessageResult"
import type { IChatRepository } from "@/domain/repository/Chat/ChatRepository"

const MOCK_DELAY_MS = 600

const MOCK_ASSISTANT_REPLY = [
  "1. Supply chain concentration: Dependence on a limited number of manufacturing partners can disrupt production if any partner faces capacity or geopolitical constraints.",
  "2. Competitive pressures: Rapid innovation cycles and aggressive pricing from peers may compress margins and market share.",
  "3. Regulatory and export controls: Changes in trade policy can restrict access to key markets and customers.",
  "4. Customer concentration: A small set of large customers can amplify revenue volatility if demand shifts.",
  "",
  "For research purposes only. Not financial advice.",
].join("\n")

function createId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

@injectable()
export default class ChatRepository implements IChatRepository {
  async sendMessage(content: string): Promise<ISendMessageResult> {
    await delay(MOCK_DELAY_MS)

    const createdAt = new Date().toISOString()

    const dto: ISendMessageResponseDTO = {
      userMessage: {
        id: createId("user"),
        role: "user",
        content,
        createdAt,
      },
      assistantMessage: {
        id: createId("assistant"),
        role: "assistant",
        content: MOCK_ASSISTANT_REPLY,
        createdAt: new Date().toISOString(),
      },
    }

    return mapSendMessageDTOToSendMessageResult(dto)
  }
}
