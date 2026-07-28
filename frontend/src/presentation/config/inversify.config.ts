import { Container } from "inversify"

import WelcomeRepository from "@/data/repository/Welcome/WelcomeRepository"
import { RepositoryTypes } from "@/domain/entities/structure/RepositoryTypes"
import { UseCaseTypes } from "@/domain/entities/structure/UseCaseTypes"
import type { IWelcomeRepository } from "@/domain/repository/Welcome/WelcomeRepository"
import GetWelcomeContentUseCase from "@/domain/interactor/Welcome/GetWelcomeContentUseCase"

const container = new Container()

container
  .bind<IWelcomeRepository>(RepositoryTypes.WelcomeRepository)
  .to(WelcomeRepository)
  .inSingletonScope()

container
  .bind<GetWelcomeContentUseCase>(UseCaseTypes.GetWelcomeContentUseCase)
  .to(GetWelcomeContentUseCase)

export { container }
