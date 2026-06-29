import { useState } from 'react'
import type { JobRecord, SkillFreq } from '../api'
import { DashboardView } from './DashboardView'
import { SkillsView } from './SkillsView'
import { TemplatesView } from './TemplatesView'
import { GeographyView } from './GeographyView'

interface Props {
  records: JobRecord[]
  skills: SkillFreq[]
  onUseTemplate: (newRecordId: string) => void
}

type View = 'analytics' | 'geography' | 'posture' | 'templates'

const VIEWS: { id: View; label: string; icon: React.ReactNode }[] = [
  {
    id: 'analytics',
    label: 'Workforce',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    id: 'geography',
    label: 'Geography',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    id: 'posture',
    label: 'Compliance',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
  },
  {
    id: 'templates',
    label: 'Templates',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
  },
]

function StatPill({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`text-sm font-bold tabular-nums ${accent ? 'text-foreground' : 'text-foreground'}`}>{value}</span>
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-5 rounded-2xl border border-dashed border-border bg-muted/10 px-8 py-24 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/60">
        <svg className="h-7 w-7 text-muted-foreground/50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">No data yet</p>
        <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
          Process your first JD in the Workspace to start seeing skill trends and compliance patterns.
        </p>
      </div>
    </div>
  )
}

export function InsightsView({ records, skills, onUseTemplate }: Props) {
  const [view, setView] = useState<View>('analytics')

  const total = records.length
  const passRate = total > 0 ? Math.round((records.filter(r => r.compliance_verdict === 'pass').length / total) * 100) : 0
  const avgScore = total > 0 ? Math.round(records.reduce((s, r) => s + r.quality_score, 0) / total) : 0
  const withPay = records.filter(r => r.pay_range_present).length

  return (
    <div className="space-y-6">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-foreground tracking-tight">Insights</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Live view of your JD portfolio — skills, compliance posture, and patterns.
          </p>
        </div>
        {total > 0 && (
          <div className="flex items-center gap-4 shrink-0 pt-0.5">
            <StatPill value={total} label={total === 1 ? 'role' : 'roles'} />
            <div className="h-3.5 w-px bg-border" />
            <StatPill value={`${passRate}%`} label="compliant" />
            <div className="h-3.5 w-px bg-border" />
            <StatPill value={`${avgScore}/100`} label="avg quality" />
            <div className="h-3.5 w-px bg-border" />
            <StatPill value={`${withPay}/${total}`} label="with pay" />
          </div>
        )}
      </div>

      {/* ── Tab navigation ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 p-1 rounded-xl bg-muted/50 w-fit">
        {VIEWS.map(v => {
          const active = v.id === view
          return (
            <button
              key={v.id}
              type="button"
              onClick={() => setView(v.id)}
              className={[
                'flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all duration-150',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                active
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              ].join(' ')}
            >
              <span className={active ? 'text-foreground' : 'text-muted-foreground/70'}>{v.icon}</span>
              {v.label}
            </button>
          )
        })}
      </div>

      {/* ── Content ────────────────────────────────────────────────────────── */}
      {records.length === 0 && view === 'analytics' ? (
        <EmptyState />
      ) : (
        <>
          {view === 'analytics' && <SkillsView skills={skills} total={records.length} records={records} />}
          {view === 'geography' && <GeographyView records={records} />}
          {view === 'posture' && <DashboardView />}
          {view === 'templates' && <TemplatesView onUseTemplate={onUseTemplate} />}
        </>
      )}
    </div>
  )
}
