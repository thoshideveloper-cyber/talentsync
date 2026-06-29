import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { RefineRun, RefineStep } from '../api'

function ScanDropdown({ step }: { step: RefineStep }) {
  const [open, setOpen] = useState(false)
  const out = step.output_ref ?? {}
  const verdict = typeof out.gate_verdict === 'string' ? out.gate_verdict : null
  const findings = typeof out.findings_count === 'number' ? out.findings_count : null
  const issues: unknown[] = Array.isArray(out.issues) ? out.issues : Array.isArray(out.findings) ? out.findings : []
  const summary = typeof out.summary === 'string' ? out.summary : null

  return (
    <div className="rounded-lg border border-border bg-muted/20 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-muted/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="font-semibold text-foreground">{step.node_name.replace(/_/g, ' ')}</span>
          {verdict && (
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
              verdict === 'pass' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
            }`}>
              {verdict === 'pass' ? 'Pass' : 'Issues found'}
            </span>
          )}
          {findings !== null && (
            <span className="text-muted-foreground">{findings} finding{findings !== 1 ? 's' : ''}</span>
          )}
        </div>
        <svg
          className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="border-t border-border px-3 py-3 space-y-2 bg-background">
          {summary && (
            <p className="text-xs text-muted-foreground">{summary}</p>
          )}
          {issues.length > 0 ? (
            <ul className="space-y-1">
              {(issues as Record<string, unknown>[]).map((issue, i) => {
                const msg = typeof issue === 'string' ? issue
                  : typeof issue.message === 'string' ? issue.message
                  : typeof issue.description === 'string' ? issue.description
                  : typeof issue.text === 'string' ? issue.text
                  : JSON.stringify(issue)
                const tier = typeof issue.tier === 'string' ? issue.tier : null
                return (
                  <li key={i} className="flex items-start gap-2 text-xs">
                    <span className={`mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full ${
                      tier === 'critical' ? 'bg-red-500' : tier === 'warning' ? 'bg-amber-500' : 'bg-blue-400'
                    }`} />
                    <span className="text-foreground">{msg}</span>
                  </li>
                )
              })}
            </ul>
          ) : (
            <p className="text-xs text-muted-foreground italic">
              {verdict === 'pass' ? 'No issues detected — JD is compliant.' : 'No detailed findings available.'}
            </p>
          )}
          {step.ts && (
            <p className="text-[10px] text-muted-foreground pt-1">
              Scanned at {new Date(step.ts).toLocaleTimeString()}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

interface Props {
  recordId: string
  roleName?: string
  /** Called when the refine run completes and a new JD version has been saved. */
  onRefined?: () => void
}

export function RefineView({ recordId, roleName, onRefined }: Props) {
  const [run, setRun] = useState<RefineRun | null>(null)
  const [steps, setSteps] = useState<RefineStep[]>([])
  const [instruction, setInstruction] = useState('')
  const [starting, setStarting] = useState(false)
  const [resuming, setResuming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  const loadStatus = async (runId: string) => {
    try {
      const [statusData, stepsData] = await Promise.all([
        api.refineStatus(recordId, runId),
        api.refineSteps(recordId, runId),
      ])
      setRun(statusData)
      setSteps(stepsData)
      if (statusData.status === 'done' || statusData.status === 'error') {
        stopPoll()
        // Notify Workspace to refresh compliance + record when a new version was saved
        if (statusData.status === 'done' && statusData.new_version_id) {
          onRefined?.()
        }
      }
    } catch { /* swallow polling errors */ }
  }

  const startPoll = (runId: string) => {
    stopPoll()
    pollRef.current = setInterval(() => void loadStatus(runId), 2000)
  }

  useEffect(() => () => stopPoll(), [])

  // Reset when record changes
  useEffect(() => {
    stopPoll(); setRun(null); setSteps([]); setError(null)
  }, [recordId])

  const handleStart = async () => {
    setStarting(true); setError(null)
    try {
      const data = await api.startRefine(recordId)
      setRun({ run_id: data.run_id, thread_id: data.thread_id, status: data.status, started_at: null, ended_at: null, latest_step: null })
      startPoll(data.run_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Start failed')
    } finally {
      setStarting(false)
    }
  }

  const handleResume = async () => {
    if (!run || !instruction.trim()) return
    setResuming(true); setError(null)
    try {
      await api.resumeRefine(recordId, run.run_id, instruction)
      setInstruction('')
      startPoll(run.run_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Resume failed')
    } finally {
      setResuming(false)
    }
  }

  const statusBadge = (s: string) => {
    const cls: Record<string, string> = {
      running: 'bg-blue-100 text-blue-800',
      paused:  'bg-yellow-100 text-yellow-800',
      done:    'bg-green-100 text-green-800',
      error:   'bg-red-100 text-red-800',
    }
    return (
      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls[s] ?? 'bg-muted text-muted-foreground'}`}>
        {s === 'running' && (
          <span className="mr-1 h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
        )}
        {s}
      </span>
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-foreground">Agentic Refine Loop</h3>
          {roleName && (
            <p className="text-xs text-muted-foreground mt-0.5">{roleName}</p>
          )}
        </div>
        {!run && (
          <button
            onClick={() => void handleStart()}
            disabled={starting}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-xs
                       font-semibold text-primary-foreground hover:bg-primary/90
                       disabled:opacity-50 transition-colors"
          >
            {starting ? (
              <span className="h-3 w-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
            Start Refine
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      {run && (
        <div className="rounded-xl border border-border bg-muted/30 p-4 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium text-muted-foreground">Status</span>
            {statusBadge(run.status)}
            {run.started_at && (
              <span className="text-xs text-muted-foreground">
                Started {new Date(run.started_at).toLocaleTimeString()}
              </span>
            )}
          </div>

          {run.latest_step && (() => {
            const out = run.latest_step.output_ref ?? {}
            const verdict = typeof out.gate_verdict === 'string' ? out.gate_verdict : null
            const findings = typeof out.findings_count === 'number' ? out.findings_count : 0
            return (
              <div className="text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{run.latest_step.node_name}</span>
                {' · '}
                {verdict && (
                  <span className={verdict === 'pass' ? 'text-green-700 font-semibold' : 'text-amber-700 font-semibold'}>
                    {verdict === 'pass' ? 'PASS' : 'WARN'} ({findings} findings)
                  </span>
                )}
              </div>
            )
          })()}

          {run.status === 'running' && (
            <div className="flex items-center gap-2 text-xs text-blue-700">
              <span className="h-3 w-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              Agent is working… (checking compliance, then it will pause if a rewrite is needed)
            </div>
          )}

          {(run.status === 'error' || run.error) && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 border-t">
              <p className="font-semibold mb-0.5">The refine run hit an error</p>
              <p className="font-mono break-all">{run.error ?? 'The agent failed — check the server logs.'}</p>
              <button
                onClick={() => { stopPoll(); setRun(null); setSteps([]); setError(null) }}
                className="mt-2 text-red-700 underline hover:no-underline font-medium"
              >
                Reset and try again
              </button>
            </div>
          )}

          {run.status === 'paused' && (
            <div className="space-y-2 border-t border-border pt-4">
              <p className="text-xs font-semibold text-foreground">
                Waiting for your rewrite instruction
              </p>
              <p className="text-xs text-muted-foreground">
                The gate found issues. Describe what to fix, then click Send &amp; Resume.
              </p>
              <textarea
                value={instruction}
                onChange={e => setInstruction(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void handleResume() } }}
                placeholder="e.g. Remove all age and gender requirements"
                rows={2}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
              />
              <button
                onClick={() => void handleResume()}
                disabled={resuming || !instruction.trim()}
                className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-xs
                           font-semibold text-primary-foreground hover:bg-primary/90
                           disabled:opacity-50 transition-colors"
              >
                {resuming && (
                  <span className="h-3 w-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                )}
                Send &amp; Resume
              </button>
            </div>
          )}

          {run.status === 'done' && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 space-y-2">
              <div className="flex items-center gap-2">
                <svg className="h-4 w-4 flex-shrink-0 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-xs font-semibold text-emerald-800">
                  {run.new_version_id
                    ? 'Rewrite complete — new compliant version saved'
                    : 'Refine complete — JD was already compliant, no changes needed'}
                </span>
              </div>
              {run.new_version_id && (
                <div className="flex gap-2 pl-6">
                  <button
                    onClick={() => api.downloadDocx(recordId, undefined, roleName).catch(e =>
                      setError(e instanceof Error ? e.message : 'Download failed'))}
                    className="text-xs font-semibold text-emerald-700 hover:underline"
                  >
                    Download corrected JD
                  </button>
                  <span className="text-emerald-400">·</span>
                  <button
                    onClick={() => api.downloadAuditReport(recordId, roleName).catch(e =>
                      setError(e instanceof Error ? e.message : 'Download failed'))}
                    className="text-xs font-semibold text-emerald-700 hover:underline"
                  >
                    Audit report
                  </button>
                </div>
              )}
            </div>
          )}

          {(run.status === 'done' || run.status === 'error') && (
            <button
              onClick={() => { stopPoll(); setRun(null); setSteps([]); setError(null) }}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors border-t border-border pt-3 w-full text-left"
            >
              ← Start a new refine run
            </button>
          )}
        </div>
      )}

      {steps.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Scan &amp; Transformations
          </h4>
          {/* First step (initial scan) shown as an expandable dropdown */}
          {steps[0].output_ref && <ScanDropdown step={steps[0]} />}
          {/* Remaining steps as a compact list */}
          {steps.slice(1).length > 0 && (
            <div className="space-y-1">
              {steps.slice(1).map(step => (
                <div key={step.id} className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${
                    step.status === 'ok' ? 'bg-green-500' :
                    step.status === 'error' ? 'bg-red-500' : 'bg-yellow-500'
                  }`} />
                  <span className="font-medium text-foreground">{step.node_name.replace(/_/g, ' ')}</span>
                  <span>·</span>
                  <span>{step.status}</span>
                  {step.ts && (
                    <span className="ml-auto">{new Date(step.ts).toLocaleTimeString()}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {run && run.status !== 'done' && run.status !== 'error' && (
        <button
          onClick={() => { stopPoll(); setRun(null); setSteps([]) }}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          ← Start new run
        </button>
      )}
    </div>
  )
}
