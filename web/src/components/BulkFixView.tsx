import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { BulkAutofixBatch } from '../api'

interface Props {
  /** The record IDs to auto-fix (all warn-verdict JDs). */
  recordIds: string[]
  /** Called when the batch completes so the parent can refresh the records list. */
  onComplete: () => void
  /** Called to dismiss this view. */
  onDismiss: () => void
}

/**
 * Batch auto-fix: applies the "Make Compliance-Pass" preset to every flagged JD.
 * HR sees a live progress list, then a results table — no instruction needed.
 */
export function BulkFixView({ recordIds, onComplete, onDismiss }: Props) {
  const [batch, setBatch] = useState<BulkAutofixBatch | null>(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  useEffect(() => () => stopPoll(), [])

  const startBatch = async () => {
    setStarting(true)
    setError(null)
    try {
      const started = await api.startBulkAutofix(recordIds)
      const initial: BulkAutofixBatch = {
        id: started.batch_id,
        status: 'running',
        total: started.total,
        completed: 0,
        failed: 0,
        preset_name: '',
        started_at: new Date().toISOString(),
        ended_at: null,
        items: recordIds.map(id => ({
          record_id: id,
          status: 'pending',
          new_verdict: null,
          high_risk_count: null,
          advisory_count: null,
          error: null,
        })),
      }
      setBatch(initial)

      // Poll every 2s
      pollRef.current = setInterval(async () => {
        try {
          const fresh = await api.bulkAutofixStatus(started.batch_id)
          setBatch(fresh)
          if (fresh.status === 'done') {
            stopPoll()
            onComplete()
          }
        } catch { /* ignore polling errors */ }
      }, 2000)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start batch')
    } finally {
      setStarting(false)
    }
  }

  const doneCount = batch?.completed ?? 0
  const failCount = batch?.failed ?? 0
  const total = batch?.total ?? recordIds.length
  const pct = total > 0 ? Math.round(((doneCount + failCount) / total) * 100) : 0

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-bold text-foreground">Auto-fix all flagged JDs</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Applies the compliance-pass preset to {recordIds.length} JD{recordIds.length !== 1 ? 's' : ''}.
            Originals are preserved — each gets a new compliant version.
          </p>
        </div>
        <button
          onClick={onDismiss}
          className="flex-shrink-0 rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          title="Dismiss"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Start prompt */}
      {!batch && !starting && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 space-y-3">
          <p className="text-sm text-amber-800">
            <span className="font-semibold">{recordIds.length} JD{recordIds.length !== 1 ? 's' : ''}</span> have compliance issues.
            AI will automatically rewrite each one to remove discriminatory language while keeping the role requirements.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => void startBatch()}
              className="rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Fix all {recordIds.length} JDs →
            </button>
            <button
              onClick={onDismiss}
              className="rounded-lg border border-border px-5 py-2.5 text-sm font-semibold text-foreground hover:bg-muted/60 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Starting spinner */}
      {starting && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-3">
          <span className="h-4 w-4 rounded-full border-2 border-muted border-t-primary animate-spin" />
          Starting batch…
        </div>
      )}

      {/* Progress */}
      {batch && (
        <div className="space-y-4">
          {/* Progress bar */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-foreground">
                {batch.status === 'done' ? 'Complete' : `Processing… ${doneCount + failCount} of ${total}`}
              </span>
              <span className="text-xs text-muted-foreground">{pct}%</span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-2 rounded-full bg-primary transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          {/* Per-record results */}
          <div className="divide-y divide-border rounded-xl border border-border overflow-hidden">
            {batch.items.map(item => (
              <div key={item.record_id} className="flex items-center gap-3 px-4 py-2.5 bg-card">
                {/* Status indicator */}
                <div className="flex-shrink-0">
                  {item.status === 'done' && item.new_verdict === 'pass' && (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100">
                      <svg className="h-3.5 w-3.5 text-emerald-600" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                        <path fillRule="evenodd" clipRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
                      </svg>
                    </div>
                  )}
                  {item.status === 'done' && item.new_verdict === 'warn' && (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-100">
                      <svg className="h-3.5 w-3.5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                          d="M12 9v2m0 4h.01" />
                      </svg>
                    </div>
                  )}
                  {item.status === 'processing' && (
                    <span className="h-6 w-6 rounded-full border-2 border-muted border-t-primary animate-spin" />
                  )}
                  {item.status === 'pending' && (
                    <div className="h-6 w-6 rounded-full border-2 border-border bg-muted/30" />
                  )}
                  {item.status === 'error' && (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-red-100">
                      <svg className="h-3.5 w-3.5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </div>
                  )}
                </div>

                {/* Record ID (truncated) */}
                <span className="text-xs font-mono text-muted-foreground flex-shrink-0">
                  {item.record_id.slice(0, 8)}…
                </span>

                {/* Result text */}
                <span className="flex-1 text-xs text-foreground truncate">
                  {item.status === 'pending' && 'Waiting…'}
                  {item.status === 'processing' && 'Rewriting…'}
                  {item.status === 'done' && item.new_verdict === 'pass' && 'Fixed — now compliant'}
                  {item.status === 'done' && item.new_verdict === 'warn' && (
                    `Rewritten — ${item.high_risk_count ?? 0} issue${item.high_risk_count !== 1 ? 's' : ''} remain`
                  )}
                  {item.status === 'error' && (
                    <span className="text-red-600">{item.error ?? 'Failed'}</span>
                  )}
                </span>

                {/* Verdict badge */}
                {item.status === 'done' && item.new_verdict && (
                  <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    item.new_verdict === 'pass'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}>
                    {item.new_verdict === 'pass' ? 'PASS' : 'WARN'}
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* Summary after completion */}
          {batch.status === 'done' && (
            <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-muted/30 px-4 py-3">
              <div className="flex items-center gap-1.5 text-sm">
                <span className="font-bold text-foreground">{doneCount}</span>
                <span className="text-muted-foreground">fixed</span>
              </div>
              {failCount > 0 && (
                <div className="flex items-center gap-1.5 text-sm">
                  <span className="font-bold text-red-700">{failCount}</span>
                  <span className="text-muted-foreground">failed</span>
                </div>
              )}
              <div className="ml-auto">
                <button
                  onClick={onDismiss}
                  className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  Done
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
