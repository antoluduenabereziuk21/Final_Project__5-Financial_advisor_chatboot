import type { IWelcomeContent } from "@/domain/entities/WelcomeContent"
import type { IWelcomeContentDTO } from "@/data/entities/WelcomeContentDTO"

export function mapWelcomeContentDTOToWelcomeContent(
  dto: IWelcomeContentDTO,
): IWelcomeContent {
  return {
    title: dto.title,
    description: dto.description,
    ctaLabel: dto.ctaLabel,
  }
}
