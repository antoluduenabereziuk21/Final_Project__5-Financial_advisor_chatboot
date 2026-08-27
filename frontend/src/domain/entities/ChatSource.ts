export interface IChatSource {
  chunkId: string
  title: string
  company: string | null
  ticker: string | null
  fiscalYear: number | null
  formType: string | null
  pageStart: number | null
  pageEnd: number | null
  textSnippet: string | null
  relevanceScore: number | null
}
