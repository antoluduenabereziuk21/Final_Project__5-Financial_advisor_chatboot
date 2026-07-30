import { Button } from "@/presentation/components/Button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/presentation/components/Card"
import { Spinner } from "@/presentation/components/Spinner"
import { Alert, AlertDescription, AlertTitle } from "@/presentation/components/Alert"

import { homeCopies, type HomeProps } from "./HomeConfig"

function Home({
  title,
  description,
  ctaLabel,
  isLoading,
  error,
  onStartConversation,
}: HomeProps) {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center bg-background px-6 py-16 text-foreground">
      <div className="flex w-full max-w-xl flex-col gap-8">
        <p className="font-heading text-sm font-medium tracking-[0.2em] text-muted-foreground uppercase">
          {homeCopies.brand}
        </p>

        {isLoading ? (
          <div
            className="flex items-center gap-3 text-muted-foreground"
            role="status"
            aria-label={homeCopies.loadingLabel}
          >
            <Spinner />
            <span>{homeCopies.loadingLabel}</span>
          </div>
        ) : null}

        {!isLoading && error ? (
          <Alert variant="destructive">
            <AlertTitle>{homeCopies.errorFallback}</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {!isLoading && !error ? (
          <Card>
            <CardHeader>
              <CardTitle>{title}</CardTitle>
              <CardDescription>{description}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                type="button"
                onClick={onStartConversation}
                aria-label={homeCopies.startConversationAriaLabel}
              >
                {ctaLabel}
              </Button>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </main>
  )
}

export { Home }
