import { ChevronDownIcon } from "lucide-react"

import { cn } from "@/lib/utils"

import {
  chatMessageSourcesCopies,
  type ChatMessageSourcesProps,
} from "./ChatMessageSourcesConfig"

function fileNameFromPath(value: string): string {
  const normalized = value.replaceAll("\\", "/")
  const segments = normalized.split("/").filter(Boolean)
  return segments.at(-1) ?? value
}

function formatPages(
  pageStart: number | null,
  pageEnd: number | null,
): string | null {
  if (pageStart === null && pageEnd === null) {
    return null
  }

  if (pageStart !== null && pageEnd !== null && pageStart !== pageEnd) {
    return `${pageStart}–${pageEnd}`
  }

  const page = pageStart ?? pageEnd
  return page !== null ? String(page) : null
}

function formatPreview(parts: Array<string | null>): string | null {
  const filtered = parts.filter((part): part is string => Boolean(part))
  return filtered.length > 0 ? filtered.join(" · ") : null
}

function SourceDetailRow({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <p className="text-xs leading-relaxed text-muted-foreground">
      <span className="font-medium text-foreground">{label}: </span>
      {value}
    </p>
  )
}

function ChatMessageSources({ sources }: ChatMessageSourcesProps) {
  if (sources.length === 0) {
    return null
  }

  return (
    <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {chatMessageSourcesCopies.sectionLabel}
      </p>
      <ol className="flex flex-col gap-2">
        {sources.map((source) => {
          const fileName = fileNameFromPath(source.title)
          const pages = formatPages(source.pageStart, source.pageEnd)
          const pagesLabel =
            source.pageStart !== null &&
            source.pageEnd !== null &&
            source.pageStart !== source.pageEnd
              ? chatMessageSourcesCopies.pagesLabel
              : chatMessageSourcesCopies.pageLabel
          const preview = formatPreview([
            source.ticker,
            source.fiscalYear !== null ? String(source.fiscalYear) : null,
            source.formType,
            pages
              ? `${pagesLabel} ${pages}`
              : null,
          ])

          return (
            <li key={source.chunkId}>
              <details
                className={cn(
                  "group rounded-xl border border-border bg-muted/30 open:bg-muted/50",
                )}
              >
                <summary
                  className={cn(
                    "flex cursor-pointer list-none items-start gap-2 px-3 py-2.5",
                    "[&::-webkit-details-marker]:hidden",
                  )}
                  aria-label={`${chatMessageSourcesCopies.expandSourceLabel}: ${fileName}`}
                >
                  <ChevronDownIcon
                    aria-hidden="true"
                    className="mt-0.5 size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-xs font-medium text-foreground">
                      {fileName}
                    </span>
                    {preview ? (
                      <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                        {preview}
                      </span>
                    ) : null}
                  </span>
                </summary>
                <div className="flex flex-col gap-0.5 border-t border-border px-3 py-2.5 pl-9">
                  <SourceDetailRow
                    label={chatMessageSourcesCopies.fileLabel}
                    value={fileName}
                  />
                  {source.company ? (
                    <SourceDetailRow
                      label={chatMessageSourcesCopies.companyLabel}
                      value={source.company}
                    />
                  ) : null}
                  {source.ticker ? (
                    <SourceDetailRow
                      label={chatMessageSourcesCopies.tickerLabel}
                      value={source.ticker}
                    />
                  ) : null}
                  {source.fiscalYear !== null ? (
                    <SourceDetailRow
                      label={chatMessageSourcesCopies.yearLabel}
                      value={String(source.fiscalYear)}
                    />
                  ) : null}
                  {source.formType ? (
                    <SourceDetailRow
                      label={chatMessageSourcesCopies.formLabel}
                      value={source.formType}
                    />
                  ) : null}
                  {pages ? (
                    <SourceDetailRow label={pagesLabel} value={pages} />
                  ) : null}
                  {source.textSnippet ? (
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      <span className="font-medium text-foreground">
                        {chatMessageSourcesCopies.excerptLabel}:{" "}
                      </span>
                      <span className="line-clamp-3">{source.textSnippet}</span>
                    </p>
                  ) : null}
                </div>
              </details>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export { ChatMessageSources }
