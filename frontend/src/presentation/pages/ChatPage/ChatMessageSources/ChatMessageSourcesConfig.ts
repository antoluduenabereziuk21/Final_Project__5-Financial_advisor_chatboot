import type { IChatSource } from "@/domain/entities/ChatSource"

export interface ChatMessageSourcesProps {
  sources: IChatSource[]
}

export const chatMessageSourcesCopies = {
  sectionLabel: "Sources",
  fileLabel: "File",
  companyLabel: "Company",
  tickerLabel: "Ticker",
  yearLabel: "Year",
  formLabel: "Form",
  pagesLabel: "Pages",
  pageLabel: "Page",
  excerptLabel: "Excerpt",
  expandSourceLabel: "Show source details",
  collapseSourceLabel: "Hide source details",
} as const
