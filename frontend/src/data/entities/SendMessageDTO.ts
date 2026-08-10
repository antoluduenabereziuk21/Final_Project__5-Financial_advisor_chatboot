export type ChatMessageRoleDTO = "user" | "assistant"

export interface IChatMessageDTO {
  id: string
  role: ChatMessageRoleDTO
  content: string
  createdAt: string
}

export interface ISendMessageResponseDTO {
  userMessage: IChatMessageDTO
  assistantMessage: IChatMessageDTO
}
