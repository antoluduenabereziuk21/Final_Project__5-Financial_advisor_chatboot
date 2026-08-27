import type { IChatMessageDTO, ISendMessageResponseDTO } from "@/data/entities/SendMessageDTO"
import type { IChatMessage } from "@/domain/entities/ChatMessage"
import type { ISendMessageResult } from "@/domain/entities/SendMessageResult"

function mapChatMessageDTOToChatMessage(dto: IChatMessageDTO): IChatMessage {
  return {
    id: dto.id,
    role: dto.role,
    content: dto.content,
    createdAt: dto.createdAt,
  }
}

export function mapSendMessageDTOToSendMessageResult(
  dto: ISendMessageResponseDTO,
): ISendMessageResult {
  return {
    userMessage: mapChatMessageDTOToChatMessage(dto.userMessage),
    assistantMessage: mapChatMessageDTOToChatMessage(dto.assistantMessage),
    conversationId: null,
  }
}
