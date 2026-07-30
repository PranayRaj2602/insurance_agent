const BASE = '/api'

export interface Claim {
  id: string
  insured_name?: string
  policy_id?: string
  date_of_loss?: string
  cause_of_loss?: string
  doc_count: number
  is_new: boolean
}

export interface Document {
  file_type: string
  path: string
  claim_id: string
}

export interface Summary {
  claim_id: string
  facts: Record<string, any>
  coverage: Record<string, any>
  risk: Record<string, any>
  timeline: Record<string, any>
  summary: string
}

export const api = {
  getClaims: (): Promise<Claim[]> =>
    fetch(`${BASE}/claims`).then(r => r.json()),

  getNextId: (): Promise<{ id: string }> =>
    fetch(`${BASE}/claims/next-id`).then(r => r.json()),

  getDocuments: (claimId: string): Promise<Document[]> =>
    fetch(`${BASE}/claims/${claimId}/documents`).then(r => r.json()),

  createClaim: (form: FormData): Promise<any> =>
    fetch(`${BASE}/claims`, { method: 'POST', body: form }).then(r => r.json()),

  ingestDocument: (claimId: string, file: File): Promise<any> => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch(`${BASE}/claims/${claimId}/ingest`, { method: 'POST', body: fd }).then(r => r.json())
  },

  streamSummarize: (claimId: string) =>
    fetch(`${BASE}/claims/${claimId}/summarize`),

  streamChat: (message: string, history: any[], claimId?: string) =>
    fetch(`${BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history, claim_id: claimId }),
    }),

  pdfUrl: (claimId: string, filename: string) =>
    `${BASE}/documents/${claimId}/${filename}`,
}
