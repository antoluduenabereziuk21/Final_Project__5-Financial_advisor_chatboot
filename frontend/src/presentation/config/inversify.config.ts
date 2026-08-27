import { Container } from "inversify"

import ChatRepository from "@/data/repository/Chat/ChatRepository"
import WelcomeRepository from "@/data/repository/Welcome/WelcomeRepository"
import { RepositoryTypes } from "@/domain/entities/structure/RepositoryTypes"
import { UseCaseTypes } from "@/domain/entities/structure/UseCaseTypes"
import type { IChatRepository } from "@/domain/repository/Chat/ChatRepository"
import type { IWelcomeRepository } from "@/domain/repository/Welcome/WelcomeRepository"
import SendMessageUseCase from "@/domain/interactor/Chat/SendMessageUseCase"
import SubmitFeedbackUseCase from "@/domain/interactor/Chat/SubmitFeedbackUseCase"
import GetWelcomeContentUseCase from "@/domain/interactor/Welcome/GetWelcomeContentUseCase"

const container = new Container()

container
  .bind<IWelcomeRepository>(RepositoryTypes.WelcomeRepository)
  .to(WelcomeRepository)
  .inSingletonScope()

container
  .bind<GetWelcomeContentUseCase>(UseCaseTypes.GetWelcomeContentUseCase)
  .to(GetWelcomeContentUseCase)

container
  .bind<IChatRepository>(RepositoryTypes.ChatRepository)
  .to(ChatRepository)
  .inSingletonScope()

container
  .bind<SendMessageUseCase>(UseCaseTypes.SendMessageUseCase)
  .to(SendMessageUseCase)

container
  .bind<SubmitFeedbackUseCase>(UseCaseTypes.SubmitFeedbackUseCase)
  .to(SubmitFeedbackUseCase)

export { container }
