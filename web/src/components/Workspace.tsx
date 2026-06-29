import { useState } from 'react'
import type { JobRecord } from '../api'
import { api } from '../api'
import { useActiveJob } from '../hooks/useActiveJob'
import { WorkspaceStepHeader } from './WorkspaceStepHeader'
import { VerdictBanner } from './VerdictBanner'
import { JdInput } from './JdInput'
import { BeforeAfter } from './BeforeAfter'
import { CompliancePanel } from './CompliancePanel'
import { ChatPanel } from './ChatPanel'
import { PresetApply } from './PresetApply'
import { RefineView } from './RefineView'

interface Props {
  records: JobRecord[]
  onChanged: (record?: JobRecord) => void
}

type Step = 1 | 2 | 3 | 4
type FixTool = 'refine' | 'transform' | 'ask'

const WORKSPACE_STEPS = [
  { n: 1, label: 'Add JD',  sublabel: 'Paste, upload, or create' },
  { n: 2, label: 'Review',  sublabel: 'Compliance & findings'    },
  { n: 3, label: 'Fix',     sublabel: 'Resolve issues'           },
  { n: 4, label: 'Export',  sublabel: 'Download files'           },
] as const

const FIX_TOOLS: { id: FixTool; label: string; description: string; icon: React.ReactNode; badge?: string }[] = [
  {
    id: 'refine',
    label: 'Auto-fix with AI',
    description: 'AI reviews every issue and rewrites the JD to remove discriminatory language while keeping your requirements.',
    badge: 'Recommended',
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    id: 'transform',
    label: 'Apply a preset',
    description: 'Use a predefined transformation to restructure or reformat your JD (e.g. "Make compliance-pass").',
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M4 6h16M4 12h8m-8 6h16" />
      </svg>
    ),
  },
  {
    id: 'ask',
    label: 'Ask about this JD',
    description: 'Get answers about specific requirements, roles, or language in this JD — grounded in the document.',
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
      </svg>
    ),
  },
]

/**
 * The recruiter's main sequential surface — redesigned for HR perspective.
 *
 * Free-navigation: once a JD is in focus, all steps are clickable.
 * Verdict-first: Step 2 shows the compliance result prominently before the diff.
 * Smart Step 3: if already compliant, surfaces a bypass; otherwise presents fix tools.
 * Persistent dock: quick-access Refine / Transform / Ask buttons always visible
 *   in the in-focus bar when a JD is loaded.
 */
export function Workspace({ records, onChanged }: Props) {
  const job = useActiveJob(records)
  const [step, setStep] = useState<Step>(1)
  const [tool, setTool] = useState<FixTool>('refine')
  const [jdExpanded, setJdExpanded] = useState(false)

  const focused = job.record
  const versionId = job.compliance?.version_id ?? focused?.version_id ?? ''

  const handleProcessed = (record: JobRecord) => {
    onChanged(record)
    job.focus(record.id)
    setStep(2)
  }

  const handleTransformed = () => {
    onChanged()
    job.refreshCompliance()
    setStep(4)  // advance to Export so the recruiter sees the result immediately
  }

  const goToTool = (t: FixTool) => {
    setTool(t)
    setStep(3)
  }

  // Free navigation: step 1 always reachable; 2-4 need a focused JD
  const canNavigateTo = (n: number) => n === 1 || !!focused

  return (
    <div className="space-y-6">

      {/* ── Step progress indicator ────────────────────────────────────────── */}
      <WorkspaceStepHeader
        steps={WORKSPACE_STEPS}
        current={step}
        canNavigateTo={canNavigateTo}
        onNavigate={n => setStep(n as Step)}
      />

      {/* ── In-focus bar ───────────────────────────────────────────────────── */}
      {focused && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
          {/* Identity */}
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground shrink-0">
              In focus
            </span>
            <span className="text-sm font-bold text-foreground truncate max-w-[14rem]">
              {focused.role}
            </span>
            {focused.ai_seniority && (
              <span className="text-xs text-muted-foreground shrink-0">· {focused.ai_seniority}</span>
            )}
            {job.compliance && (
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold shrink-0 ${
                job.compliance.verdict === 'pass'
                  ? 'bg-emerald-100 text-emerald-800'
                  : job.compliance.high_risk_count > 0
                    ? 'bg-red-100 text-red-800'
                    : 'bg-amber-100 text-amber-800'
              }`}>
                {job.compliance.verdict === 'pass'
                  ? 'Compliant'
                  : `${job.compliance.high_risk_count + job.compliance.advisory_count} issue${
                      job.compliance.high_risk_count + job.compliance.advisory_count !== 1 ? 's' : ''
                    }`}
              </span>
            )}
          </div>

          {/* Tool shortcuts */}
          <div className="hidden sm:flex items-center gap-1">
            {FIX_TOOLS.map(t => (
              <button
                key={t.id}
                onClick={() => goToTool(t.id)}
                title={t.label}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-semibold transition-colors border ${
                  step === 3 && tool === t.id
                    ? 'bg-primary/8 border-primary/30 text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/60'
                }`}
              >
                {t.icon}
                <span className="hidden lg:inline">{t.label.split(' ')[0]}</span>
              </button>
            ))}
          </div>

          {/* Role switcher */}
          {records.length > 1 && (
            <select
              className="max-w-[13rem] rounded-lg border border-input bg-background px-2.5 py-1.5 text-xs font-medium
                         focus:outline-none focus:ring-2 focus:ring-primary/50 text-foreground"
              value={focused.id}
              onChange={e => { job.focus(e.target.value); setStep(2) }}
            >
              {records.map(r => <option key={r.id} value={r.id}>{r.role}</option>)}
            </select>
          )}
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* Step 1 — Add a JD                                                  */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {step === 1 && (
        <section className="space-y-5">
          <div>
            <h2 className="text-lg font-bold text-foreground">
              {records.length === 0 ? 'Add your first job description' : 'Add another job description'}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Every JD is normalized, compliance-checked, and stored — choose how you'd like to add it.
            </p>
          </div>

          <JdInput
            existingHashes={new Set(records.map(r => r.content_hash))}
            onProcessed={handleProcessed}
          />

          {records.length > 0 && (
            <button
              onClick={() => {
                if (!focused) job.focus(records[records.length - 1].id)
                setStep(2)
              }}
              className="text-sm font-semibold text-primary hover:underline"
            >
              Review an existing role instead →
            </button>
          )}
        </section>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* Step 2 — Review                                                     */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {step === 2 && focused && (
        <section className="space-y-6">
          <div>
            <h2 className="text-lg font-bold text-foreground">Compliance check results</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Review the verdict for <span className="font-semibold text-foreground">{focused.role}</span> and decide what to do next.
            </p>
          </div>

          {/* VERDICT FIRST — hero banner */}
          <VerdictBanner compliance={job.compliance} loading={job.complianceLoading} />

          {/* Primary actions right after verdict */}
          {!job.complianceLoading && job.compliance && (
            <div className="flex flex-wrap items-center gap-3">
              {job.compliance.verdict === 'pass' ? (
                <>
                  <button
                    onClick={() => setStep(4)}
                    className="rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
                  >
                    Download now →
                  </button>
                  <button
                    onClick={() => setStep(3)}
                    className="rounded-lg border border-border px-5 py-2.5 text-sm font-semibold text-foreground hover:bg-muted/60 transition-colors"
                  >
                    Review tools anyway
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => goToTool('refine')}
                    className="rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
                  >
                    Auto-fix issues →
                  </button>
                  <button
                    onClick={() => setStep(3)}
                    className="rounded-lg border border-border px-5 py-2.5 text-sm font-semibold text-foreground hover:bg-muted/60 transition-colors"
                  >
                    See all fix options
                  </button>
                  <button
                    onClick={() => setStep(4)}
                    className="text-sm font-semibold text-muted-foreground hover:text-foreground hover:underline"
                  >
                    Export anyway
                  </button>
                </>
              )}
            </div>
          )}

          {/* Compliance findings detail */}
          <div>
            <h3 className="mb-3 text-sm font-bold text-foreground">Detailed findings</h3>
            <CompliancePanel
              recordId={focused.id}
              versionId={versionId}
              result={job.compliance}
              loading={job.complianceLoading}
              autoLoad
            />
          </div>

          {/* Collapsible: Phase 1 normalized JD text (always the original upload, never the AI-rewrite) */}
          <div className="rounded-xl border border-border bg-card">
            <button
              type="button"
              onClick={() => setJdExpanded(v => !v)}
              className="flex w-full items-center justify-between px-5 py-3.5 text-sm font-semibold text-foreground hover:bg-muted/30 transition-colors rounded-xl"
            >
              <span>
                View original JD text
                {focused.initial_version_id && (
                  <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                    Phase 1
                  </span>
                )}
              </span>
              <svg
                className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${jdExpanded ? 'rotate-180' : ''}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {jdExpanded && (() => {
              // Always show the Phase 1 original text here — after an AI rewrite,
              // initial_raw_jd holds the original while raw_jd has the rewritten version.
              const phase1Text = focused.initial_raw_jd ?? focused.raw_jd
              const phase1VerId = focused.initial_version_id ?? focused.version_id
              return (
                <div className="border-t border-border px-5 pb-5 pt-4">
                  {focused.initial_version_id && (
                    <p className="mb-3 text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2 border border-amber-200">
                      Showing the original JD as uploaded (Phase 1). The AI-fixed version is available in Export.
                    </p>
                  )}
                  <BeforeAfter
                    rawText={phase1Text}
                    record={focused}
                    onDownload={() => void api.downloadDocx(focused.id, phase1VerId, focused.role).catch(e => console.error('Download failed', e))}
                    onCopy={() => navigator.clipboard.writeText(phase1Text)}
                  />
                </div>
              )
            })()}
          </div>
        </section>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* Step 3 — Fix                                                        */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {step === 3 && focused && (
        <section className="space-y-5">
          <div>
            <h2 className="text-lg font-bold text-foreground">Fix &amp; improve</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Choose how you'd like to work on <span className="font-semibold text-foreground">{focused.role}</span>.
            </p>
          </div>

          {/* Smart: if already compliant, surface bypass prominently */}
          {job.compliance?.verdict === 'pass' && (
            <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4">
              <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-600" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                <path fillRule="evenodd" clipRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
              </svg>
              <div>
                <p className="text-sm font-semibold text-emerald-800">Nothing to fix — this JD is already compliant</p>
                <p className="mt-0.5 text-xs text-emerald-700">
                  You can skip straight to export, or use the tools below to further refine or ask questions.
                </p>
                <button
                  onClick={() => setStep(4)}
                  className="mt-2.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700 transition-colors"
                >
                  Go to export →
                </button>
              </div>
            </div>
          )}

          {/* Tool selector cards */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {FIX_TOOLS.map(t => {
              const selected = tool === t.id
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTool(t.id)}
                  className={[
                    'relative flex flex-col items-start gap-2 rounded-xl border p-4 text-left',
                    'transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                    selected
                      ? 'border-primary bg-primary/5 shadow-sm'
                      : 'border-border bg-card hover:border-primary/40 hover:bg-muted/30',
                  ].join(' ')}
                >
                  {selected && (
                    <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-primary">
                      <svg className="h-3 w-3 text-primary-foreground" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                        <path fillRule="evenodd" clipRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
                      </svg>
                    </span>
                  )}

                  {t.badge && (
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
                      {t.badge}
                    </span>
                  )}

                  <span className={selected ? 'text-primary' : 'text-muted-foreground'}>
                    {t.icon}
                  </span>

                  <div>
                    <p className={`text-sm font-semibold ${selected ? 'text-primary' : 'text-foreground'}`}>
                      {t.label}
                    </p>
                    <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                      {t.description}
                    </p>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Active tool panel */}
          <div className="rounded-xl border border-border bg-card p-5">
            {tool === 'refine' && (
              <RefineView
                recordId={focused.id}
                roleName={focused.role}
                onRefined={handleTransformed}
              />
            )}
            {tool === 'transform' && (
              <PresetApply
                recordId={focused.id}
                currentVersionId={versionId}
                roleName={focused.role}
                onTransformed={handleTransformed}
              />
            )}
            {tool === 'ask' && (
              <ChatPanel recordId={focused.id} roleName={focused.role} />
            )}
          </div>

          <button
            onClick={() => setStep(4)}
            className="rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Done — export →
          </button>
        </section>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* Step 4 — Export                                                     */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {step === 4 && focused && (() => {
        const hasAiFix = !!focused.initial_version_id  // true when a rewrite was applied
        const phase1VerId = focused.initial_version_id  // original upload version
        return (
          <section className="space-y-5">
            <div>
              <h2 className="text-lg font-bold text-foreground">Export your JD</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {hasAiFix
                  ? 'Your JD has been rewritten by AI — download the fixed version or the original for comparison.'
                  : 'Download the ready-to-post JD or the full audit report for your records.'}
              </p>
            </div>

            {/* AI-Fixed version (primary) — shown only when a rewrite exists */}
            {hasAiFix && (
              <div className="rounded-xl border-2 border-emerald-200 bg-emerald-50/50 p-1">
                <div className="rounded-lg px-2 py-1 mb-2">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-700">
                    AI-Fixed Output
                  </span>
                  <span className="ml-2 text-[10px] text-emerald-600">Compliance rewrite applied</span>
                </div>
                <button
                  type="button"
                  onClick={() => void api.downloadDocx(focused.id, undefined, focused.role).catch(e => console.error('Download failed', e))}
                  className="flex items-center gap-4 rounded-xl border border-emerald-200 bg-white px-5 py-4 text-left w-full
                             hover:border-emerald-400 hover:bg-emerald-50 transition-colors group"
                >
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-100 group-hover:bg-emerald-200 transition-colors">
                    <svg className="h-5 w-5 text-emerald-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                        d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-bold text-foreground">Download AI-Fixed JD</p>
                    <p className="text-xs text-muted-foreground">Compliance-rewritten, ready to post (.docx)</p>
                  </div>
                </button>
              </div>
            )}

            <div className={`grid grid-cols-1 gap-4 ${hasAiFix ? 'sm:grid-cols-2' : 'sm:grid-cols-2'}`}>
              {/* Phase 1 / Original JD */}
              <button
                type="button"
                onClick={() => void api.downloadDocx(focused.id, phase1VerId, focused.role).catch(e => console.error('Download failed', e))}
                className="flex items-center gap-4 rounded-xl border border-border bg-card px-5 py-4 text-left w-full
                           hover:border-primary/40 hover:bg-muted/30 transition-colors group"
              >
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
                  <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-bold text-foreground">
                    {hasAiFix ? 'Original JD (Phase 1)' : 'Download JD'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {hasAiFix ? 'As uploaded, with review notes (.docx)' : 'Normalized, with compliance notes (.docx)'}
                  </p>
                </div>
              </button>

              {/* Audit Report */}
              <button
                type="button"
                onClick={() => void api.downloadAuditReport(focused.id, focused.role).catch(e => console.error('Download failed', e))}
                className="flex items-center gap-4 rounded-xl border border-border bg-card px-5 py-4 text-left w-full
                           hover:border-primary/40 hover:bg-muted/30 transition-colors group"
              >
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-muted group-hover:bg-muted/70 transition-colors">
                  <svg className="h-5 w-5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-bold text-foreground">Audit Report</p>
                  <p className="text-xs text-muted-foreground">Findings, methodology & provenance for legal (.docx)</p>
                </div>
              </button>
            </div>

            <button
              onClick={() => { job.clear(); setStep(1) }}
              className="text-sm font-semibold text-primary hover:underline"
            >
              ← Start another JD
            </button>
          </section>
        )
      })()}

      {/* ── Fallback: step requires a JD but none is focused ──────────────── */}
      {step !== 1 && !focused && (
        <div className="rounded-xl border border-dashed border-border px-6 py-10 text-center">
          <p className="text-sm text-muted-foreground">No JD selected.</p>
          <button
            onClick={() => setStep(1)}
            className="mt-3 text-sm font-semibold text-primary hover:underline"
          >
            ← Add a JD to get started
          </button>
        </div>
      )}

    </div>
  )
}
