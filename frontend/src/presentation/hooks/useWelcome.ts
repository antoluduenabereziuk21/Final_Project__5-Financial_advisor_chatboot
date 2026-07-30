import { useEffect, useState } from "react"

import type { IWelcomeContent } from "@/domain/entities/WelcomeContent"
import { UseCaseTypes } from "@/domain/entities/structure/UseCaseTypes"
import type GetWelcomeContentUseCase from "@/domain/interactor/Welcome/GetWelcomeContentUseCase"
import { container } from "@/presentation/config/inversify.config"

const useWelcomeCopies = {
  loadError: "Unable to load welcome content.",
} as const

export function useWelcome() {
  const [content, setContent] = useState<IWelcomeContent | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    async function loadWelcome() {
      setIsLoading(true)
      setError(null)

      try {
        const useCase = container.get<GetWelcomeContentUseCase>(
          UseCaseTypes.GetWelcomeContentUseCase,
        )
        const result = await useCase.execute()

        if (isMounted) {
          setContent(result)
        }
      } catch {
        if (isMounted) {
          setError(useWelcomeCopies.loadError)
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    void loadWelcome()

    return () => {
      isMounted = false
    }
  }, [])

  return {
    content,
    isLoading,
    error,
  }
}
