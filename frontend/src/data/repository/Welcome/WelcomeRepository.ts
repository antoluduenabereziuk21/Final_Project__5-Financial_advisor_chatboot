import { injectable } from "inversify"

import { mapWelcomeContentDTOToWelcomeContent } from "@/data/adapters/mapWelcomeContentDTOToWelcomeContent"
import type { IWelcomeContentDTO } from "@/data/entities/WelcomeContentDTO"
import type { IWelcomeContent } from "@/domain/entities/WelcomeContent"
import type { IWelcomeRepository } from "@/domain/repository/Welcome/WelcomeRepository"

@injectable()
export default class WelcomeRepository implements IWelcomeRepository {
  async getWelcomeContent(): Promise<IWelcomeContent> {
    const dto: IWelcomeContentDTO = {
      title: "Financial Advisor",
      description:
        "Get clear, practical guidance for your money decisions in a focused chat.",
      ctaLabel: "Start conversation",
    }

    return mapWelcomeContentDTOToWelcomeContent(dto)
  }
}
