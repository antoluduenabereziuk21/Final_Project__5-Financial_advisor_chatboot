import { injectable } from "inversify"

import httpClient from "@/data/provider/httpClient"
import { mapWelcomeContentDTOToWelcomeContent } from "@/data/adapters/mapWelcomeContentDTOToWelcomeContent"
import type { IWelcomeContentDTO } from "@/data/entities/WelcomeContentDTO"
import type { IWelcomeContent } from "@/domain/entities/WelcomeContent"
import type { IWelcomeRepository } from "@/domain/repository/Welcome/WelcomeRepository"

@injectable()
export default class WelcomeRepository implements IWelcomeRepository {
  async getWelcomeContent(): Promise<IWelcomeContent> {
    try {
      const response = await httpClient.get<IWelcomeContentDTO>("/api/welcome")
      return mapWelcomeContentDTOToWelcomeContent(response.data)
    } catch {
      const fallbackDto: IWelcomeContentDTO = {
        title: "Financial Advisor",
        description:
          "Get clear, practical guidance for your money decisions in a focused chat.",
        ctaLabel: "Start conversation",
      }
      return mapWelcomeContentDTOToWelcomeContent(fallbackDto)
    }
  }
}
