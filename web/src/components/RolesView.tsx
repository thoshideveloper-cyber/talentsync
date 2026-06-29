import { useState } from 'react'
import type { JobRecord } from '../api'
import { Board } from './Board'
import { LevelingView } from './LevelingView'
import { BulkFixView } from './BulkFixView'

interface Props {
  records: JobRecord[]
  onOpenRole: (recordId: string) => void
  /** Called after batch auto-fix completes so App can refresh records. */
  onBulkFixed?: () => void
}

/**
 * Role intelligence table.
 * "All roles" and "Leveling flags" views, plus a batch "Fix all flagged" action
 * when warn-verdict JDs are present.
 */
export function RolesView({ records, onOpenRole, onBulkFixed }: Props) {
  const [view, setView] = useState<'all' | 'leveling'>('all')
  const [showBulkFix, setShowBulkFix] = useState(false)

  const flaggedIds = records
    .filter(r => r.compliance_verdict === 'warn')
    .map(r => r.id)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-foreground">Role intelligence</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {records.length} processed role{records.length !== 1 ? 's' : ''}.
            {flaggedIds.length > 0 && (
              <span className="ml-1 text-amber-700 font-medium">
                {flaggedIds.length} need{flaggedIds.length === 1 ? 's' : ''} attention.
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Batch fix button — only when there are flagged JDs */}
          {flaggedIds.length > 0 && !showBulkFix && (
            <button
              onClick={() => setShowBulkFix(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-xs
                         font-semibold text-white hover:bg-amber-600 transition-colors"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Auto-fix all flagged ({flaggedIds.length})
            </button>
          )}

          {/* View toggle */}
          <select
            value={view}
            onChange={e => setView(e.target.value as 'all' | 'leveling')}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm font-medium
                       focus:outline-none focus:ring-2 focus:ring-primary/50 text-foreground"
          >
            <option value="all">All roles</option>
            <option value="leveling">Leveling flags</option>
          </select>
        </div>
      </div>

      {/* Batch fix panel */}
      {showBulkFix && (
        <div className="rounded-xl border border-border bg-card p-5">
          <BulkFixView
            recordIds={flaggedIds}
            onComplete={() => {
              setShowBulkFix(false)
              onBulkFixed?.()
            }}
            onDismiss={() => setShowBulkFix(false)}
          />
        </div>
      )}

      {view === 'all'
        ? <Board records={records} onOpenRole={onOpenRole} />
        : <LevelingView records={records} />}
    </div>
  )
}
