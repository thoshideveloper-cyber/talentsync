export interface JobRecord {
  id: string
  role: string
  input_format: string
  raw_jd: string
  one_line_summary: string
  ai_seniority: string
  required_skills: string[]
  raw_text_justification: string
  native_label: string | null
  is_verified: boolean
  audit_mismatch: boolean
  bias_flags: string[]
  pay_range_present: boolean
  quality_score: number
  score_breakdown: string[]
  content_hash: string
  status: string
}

export interface KpiData {
  total: number
  flagged_for_review: string
  leveling_flags: string
  with_pay_range: string
  verified: string
  hallucination_note: string
}

export interface SkillFreq {
  skill: string
  count: number
}

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  records: (): Promise<JobRecord[]> => get('/records'),
  record: (id: string): Promise<JobRecord> => get(`/records/${id}`),
  kpis: (): Promise<KpiData> => get('/kpis'),
  skills: (): Promise<SkillFreq[]> => get('/skills'),

  extract: async (text: string): Promise<JobRecord> => {
    const res = await fetch(`${BASE}/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    return res.json() as Promise<JobRecord>
  },

  extractFile: async (file: File): Promise<JobRecord> => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/extract/file`, { method: 'POST', body: form })
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<JobRecord>
  },

  docxUrl: (id: string) => `${BASE}/records/${id}/docx`,
  csvUrl: () => `${BASE}/export.csv`,

  extractDocx: async (text: string): Promise<Blob> => {
    const res = await fetch(`${BASE}/extract/docx`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    return res.blob()
  },
}
