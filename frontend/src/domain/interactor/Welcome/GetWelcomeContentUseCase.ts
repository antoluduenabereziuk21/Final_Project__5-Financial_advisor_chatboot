import { decorate, inject, injectable } from "inversify"

import { RepositoryTypes } from "@/domain/entities/structure/RepositoryTypes"
import type { IWelcomeContent } from "@/domain/entities/WelcomeContent"
import type { IWelcomeRepository } from "@/domain/repository/Welcome/WelcomeRepository"

@injectable()
export default class GetWelcomeContentUseCase {
  private readonly welcomeRepository!: IWelcomeRepository

  async execute(): Promise<IWelcomeContent> {
    return this.welcomeRepository.getWelcomeContent()
  }
}

decorate(
  inject(RepositoryTypes.WelcomeRepository) as PropertyDecorator,
  GetWelcomeContentUseCase,
  "welcomeRepository",
)
