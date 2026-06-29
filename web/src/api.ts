import { authStore, type AuthUser } from './lib/auth'

export interface ComplianceCheck {
  id?: string
  rule_id: string
  risk_tier: 'high_risk' | 'advisory'
  result: 'warn' | 'fail' | 'pass'
  evidence_span: string | null
  citation: string | null
  checked_at: string | null
}

export interface ComplianceResult {
  version_id: string
  verdict: 'pass' | 'warn'
  high_risk_count: number
  advisory_count: number
  checks: ComplianceCheck[]
}

export interface BulkAuditFinding {
  rule_id: string
  risk_tier: 'high_risk' | 'advisory'
  result: 'warn'
  evidence_span: string
  citation: string
}

export interface BulkAuditJdResult {
  index: number
  label: string
  verdict: 'pass' | 'warn'
  high_risk_count: number
  advisory_count: number
  findings: BulkAuditFinding[]
}

export interface BulkAuditResult {
  total: number
  high_risk_jds: number
  advisory_only_jds: number
  clean_jds: number
  at_risk_jds: number
  rules_triggered: Record<string, number>
  verdict_summary: string
  results: BulkAuditJdResult[]
}

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
  // Phase 0 additions (optional so existing consumers don't break)
  version_id?: string
  created_at?: string
  job_status?: string
  // Phase 1 compliance additions
  compliance_checks?: ComplianceCheck[]
  compliance_verdict?: 'pass' | 'warn'
  // Phase 2 rewrite tracking — set only when current version differs from original upload
  initial_version_id?: string
  initial_raw_jd?: string
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

export interface VersionSummary {
  version_id: string
  parent_version_id: string | null
  content_hash: string
  source: string
  change_note: string | null
  ai_seniority: string | null
  quality_score: number
  status: string
  created_at: string | null
}

// ── Batch auto-fix ────────────────────────────────────────────────────────────

export interface BulkAutofixItem {
  record_id: string
  status: 'pending' | 'processing' | 'done' | 'error'
  new_verdict: 'pass' | 'warn' | null
  high_risk_count: number | null
  advisory_count: number | null
  error: string | null
}

export interface BulkAutofixBatch {
  id: string
  status: 'running' | 'done'
  total: number
  completed: number
  failed: number
  preset_name: string
  started_at: string
  ended_at: string | null
  items: BulkAutofixItem[]
}

// ── Phase 3: Intake ────────────────────────────────────────────────────────────

export interface IntakeMeta {
  level: string
  location: string
  pay_band: string
  must_haves: string[]
}

export interface ComplianceSummary {
  verdict: 'pass' | 'warn'
  high_risk_count: number
  advisory_count: number
}

export interface IntakeResult extends JobRecord {
  compliance_summary: ComplianceSummary
  intake_meta: IntakeMeta
}

export interface IntakeRequest {
  role: string
  level: string
  must_haves: string[]
  location: string
  pay_band: string
  notes?: string
}

// ── Phase 5 Channel A2: Q&A ───────────────────────────────────────────────────

export interface QAResult {
  answer: string
  not_in_jd: boolean
  record_id: string
  version_id: string
}

// ── Phase 5 Channel B: Presets ────────────────────────────────────────────────

export interface Preset {
  id: string
  name: string
  kind: string
  active: boolean
  created_at: string | null
}

export interface TransformMeta {
  preset_id: string
  preset_name: string
  parent_version_id: string
}

export interface TransformResult extends JobRecord {
  compliance_summary: ComplianceSummary
  transform_meta: TransformMeta
}

// ── Phase 6 Feature G: Dashboard ─────────────────────────────────────────────

export interface PostureTrendEntry {
  week: string
  pass_rate: number | null
}

export interface PostureTopRule {
  rule_id: string
  count: number
}

export interface PostureOverride {
  actor_email: string
  action: string
  ts: string | null
  detail: unknown
}

export interface PostureData {
  overall_pass_rate: number
  total_versions_checked: number
  top_rules: PostureTopRule[]
  trend: PostureTrendEntry[]
  recent_overrides: PostureOverride[]
}

// ── Phase 6 Feature E: Templates ─────────────────────────────────────────────

export interface TemplateRecord {
  version_id: string
  job_id: string
  role: string
  ai_seniority: string
  required_skills: string[]
  source: string
  created_at: string | null
  created_by_email: string | null
}

export interface CloneResult extends JobRecord {
  cloned_from_version_id: string
}

// ── Phase 6 Feature I: Pay Hints ─────────────────────────────────────────────

export interface PayHintResult {
  matched_count: number
  sample_roles: string[]
  hint: string
}

// ── WS2: LangGraph Refine ─────────────────────────────────────────────────────

export interface RefineStep {
  id: string
  node_name: string
  status: string
  input_ref: Record<string, unknown> | null
  output_ref: Record<string, unknown> | null
  error: string | null
  ts: string | null
}

export interface RefineRun {
  run_id: string
  thread_id: string
  status: string
  started_at: string | null
  ended_at: string | null
  latest_step: RefineStep | null
  /** Surfaced from the newest errored step so the UI never hangs silently. */
  error?: string | null
  /** Set when the run completes and the refined JD was persisted as a new version. */
  new_version_id?: string | null
}

const BASE = '/api'

function authHeaders(): Record<string, string> {
  const token = authStore.getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() })
  if (res.status === 401) {
    authStore.clear()
    window.location.reload()
    throw new Error('Session expired')
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

/**
 * Download a file from an authenticated endpoint. A bare <a href> / window.open
 * cannot attach the Bearer token, so those silently 401 — always go through here.
 */
async function download(path: string, filename: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() })
  if (res.status === 401) {
    authStore.clear(); window.location.reload(); throw new Error('Session expired')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { detail?: string }
    throw new Error(body.detail ?? `Download failed (${res.status})`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────────
  login: async (email: string, password: string): Promise<{ token: string; user: AuthUser }> => {
    const res = await fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? 'Login failed')
    }
    const data = await res.json() as { access_token: string; user: AuthUser }
    return { token: data.access_token, user: data.user }
  },

  me: (): Promise<AuthUser> => get('/auth/me'),

  // ── Records ───────────────────────────────────────────────────────────────
  records: (): Promise<JobRecord[]> => get('/records'),
  record: (id: string): Promise<JobRecord> => get(`/records/${id}`),
  versions: (id: string): Promise<VersionSummary[]> => get(`/records/${id}/versions`),

  kpis: (): Promise<KpiData> => get('/kpis'),
  skills: (): Promise<SkillFreq[]> => get('/skills'),

  extract: async (text: string): Promise<JobRecord> => {
    const res = await fetch(`${BASE}/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ text }),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    return res.json() as Promise<JobRecord>
  },

  extractFile: async (file: File): Promise<JobRecord> => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/extract/file`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<JobRecord>
  },

  // Authenticated downloads (Bearer token can't ride on a bare href / window.open)
  downloadDocx: (id: string, versionId?: string) =>
    download(
      `/records/${id}/docx${versionId ? `?version_id=${encodeURIComponent(versionId)}` : ''}`,
      `${id}_corrected.docx`,
    ),
  downloadAuditReport: (id: string) => download(`/records/${id}/audit-report`, `${id}_audit_report.docx`),
  downloadCsv: () => download('/export.csv', 'talentsync_export.csv'),

  extractDocx: async (text: string): Promise<Blob> => {
    const res = await fetch(`${BASE}/extract/docx`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ text }),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    return res.blob()
  },

  // ── Phase 1: Compliance ────────────────────────────────────────────────────
  complianceChecks: (recordId: string): Promise<ComplianceResult> =>
    get(`/records/${recordId}/compliance`),

  complianceOverride: async (
    recordId: string,
    versionId: string,
    justification: string,
  ): Promise<{ status: string }> => {
    const res = await fetch(`${BASE}/records/${recordId}/compliance/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ version_id: versionId, justification }),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<{ status: string }>
  },

  // ── Phase 2: Bulk audit ───────────────────────────────────────────────────
  bulkAudit: async (jds: { label: string; text: string }[]): Promise<BulkAuditResult> => {
    const res = await fetch(`${BASE}/bulk-audit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ jds }),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<BulkAuditResult>
  },

  bulkAuditFiles: async (files: File[]): Promise<BulkAuditResult> => {
    const form = new FormData()
    for (const f of files) form.append('files', f)
    const res = await fetch(`${BASE}/bulk-audit/files`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<BulkAuditResult>
  },

  bulkAuditExportCsv: async (jds: { label: string; text: string }[]): Promise<Blob> => {
    const res = await fetch(`${BASE}/bulk-audit/export.csv`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ jds }),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    return res.blob()
  },

  // ── Phase 3: Intake ──────────────────────────────────────────────────────────
  intakeDraft: async (req: IntakeRequest): Promise<IntakeResult> => {
    const res = await fetch(`${BASE}/intake`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(req),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<IntakeResult>
  },

  // ── Phase 5 Channel A2: Grounded Q&A ─────────────────────────────────────────
  askAboutJd: async (recordId: string, question: string): Promise<QAResult> => {
    const res = await fetch(`${BASE}/records/${recordId}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ question }),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<QAResult>
  },

  // ── Phase 5 Channel B: Presets ────────────────────────────────────────────────
  listPresets: (): Promise<Preset[]> => get('/presets'),

  createPreset: async (name: string, prompt_text: string, kind = 'transform'): Promise<Preset> => {
    const res = await fetch(`${BASE}/presets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ name, kind, prompt_text }),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<Preset>
  },

  // ── Phase 6 Feature G: Dashboard ──────────────────────────────────────────
  dashboardPosture: (): Promise<PostureData> => get('/dashboard/posture'),

  // ── Phase 6 Feature E: Templates ──────────────────────────────────────────
  listTemplates: (limit = 50, offset = 0): Promise<TemplateRecord[]> =>
    get(`/templates?limit=${limit}&offset=${offset}`),

  cloneTemplate: async (versionId: string): Promise<CloneResult> => {
    const res = await fetch(`${BASE}/templates/${versionId}/clone`, {
      method: 'POST',
      headers: authHeaders(),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<CloneResult>
  },

  // ── Phase 6 Feature I: Pay Hints ──────────────────────────────────────────
  payHints: (role: string, seniority?: string): Promise<PayHintResult> => {
    const q = new URLSearchParams({ role })
    if (seniority) q.set('seniority', seniority)
    return get(`/pay-hints?${q.toString()}`)
  },

  // ── WS2: LangGraph Refine ─────────────────────────────────────────────────
  startRefine: async (recordId: string): Promise<{ run_id: string; thread_id: string; status: string }> => {
    const res = await fetch(`${BASE}/records/${recordId}/refine/start`, {
      method: 'POST',
      headers: authHeaders(),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<{ run_id: string; thread_id: string; status: string }>
  },

  refineStatus: (recordId: string, runId: string): Promise<RefineRun> =>
    get(`/records/${recordId}/refine/${runId}/status`),

  resumeRefine: async (recordId: string, runId: string, instruction: string): Promise<{ status: string }> => {
    const res = await fetch(`${BASE}/records/${recordId}/refine/${runId}/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ instruction }),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<{ status: string }>
  },

  refineSteps: (recordId: string, runId: string): Promise<RefineStep[]> =>
    get(`/records/${recordId}/refine/${runId}/steps`),

  applyTransform: async (recordId: string, presetId: string): Promise<TransformResult> => {
    const res = await fetch(`${BASE}/records/${recordId}/transform`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ preset_id: presetId }),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<TransformResult>
  },

  startBulkAutofix: async (recordIds: string[], presetId?: string): Promise<{ batch_id: string; status: string; total: number }> => {
    const res = await fetch(`${BASE}/bulk-autofix`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ record_ids: recordIds, preset_id: presetId ?? null }),
    })
    if (res.status === 401) { authStore.clear(); window.location.reload(); throw new Error('Session expired') }
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<{ batch_id: string; status: string; total: number }>
  },

  bulkAutofixStatus: (batchId: string): Promise<BulkAutofixBatch> =>
    get(`/bulk-autofix/${batchId}`),
}
