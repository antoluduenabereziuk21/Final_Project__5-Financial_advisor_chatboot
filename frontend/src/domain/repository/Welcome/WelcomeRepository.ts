import type { IWelcomeContent } from "@/domain/entities/WelcomeContent"

export interface IWelcomeRepository {
  getWelcomeContent(): Promise<IWelcomeContent>
}
