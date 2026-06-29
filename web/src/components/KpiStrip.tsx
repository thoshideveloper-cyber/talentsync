import type { KpiData } from '../api'

interface Props {
  kpis: KpiData
}

function parseFrac(s: string): [number, number] | null {
  const m = s.match(/^(\d+) of (\d+)$/)
  return m ? [parseInt(m[1]), parseInt(m[2])] : null
}

type StatKind = 'neutral'

interface Stat {
  label:  string
  value:  string | number
  detail: string | null
  kind:   StatKind
}

function buildStats(kpis: KpiData): Stat[] {
  const toDisplay = (raw: string | number): string | number => {
    if (typeof raw === 'string') {
      const frac = parseFrac(raw)
      if (frac) return `${Math.round((frac[0] / Math.max(frac[1], 1)) * 100)}%`
    }
    return raw
  }

  const toDetail = (raw: string | number): string | null => {
    if (typeof raw === 'string') {
      const frac = parseFrac(raw)
      if (frac) return `${frac[0]} of ${frac[1]}`
    }
    return null
  }

  return [
    {
      label: 'Roles processed',
      value: toDisplay(kpis.total),
      detail: toDetail(kpis.total),
      kind: 'neutral',
    },
    {
      label: 'Bias flagged',
      value: toDisplay(kpis.flagged_for_review),
      detail: toDetail(kpis.flagged_for_review),
      kind: 'neutral',
    },
    {
      label: 'Leveling flags',
      value: toDisplay(kpis.leveling_flags),
      detail: toDetail(kpis.leveling_flags),
      kind: 'neutral',
    },
    {
      label: 'With pay range',
      value: toDisplay(kpis.with_pay_range),
      detail: toDetail(kpis.with_pay_range),
      kind: 'neutral',
    },
    {
      label: 'Quotes verified',
      value: toDisplay(kpis.verified),
      detail: toDetail(kpis.verified),
      kind: 'neutral',
    },
  ]
}

export function KpiStrip({ kpis }: Props) {
  const stats = buildStats(kpis)

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="flex flex-wrap divide-y divide-border sm:divide-y-0 sm:divide-x sm:divide-border">
        {stats.map((stat) => (
          <StatCell key={stat.label} stat={stat} />
        ))}
      </div>
    </div>
  )
}

function StatCell({ stat }: { stat: Stat }) {
  return (
    <div className="flex-1 min-w-[9rem] px-5 py-4">
      <p className="text-xs text-muted-foreground leading-none mb-2.5">
        {stat.label}
      </p>
      <div className="flex items-baseline gap-1.5">
        <span className="text-[1.625rem] font-bold leading-none tabular-nums">
          {stat.value}
        </span>
      </div>
      {stat.detail && (
        <p className="mt-1.5 text-[11px] text-muted-foreground tabular-nums">
          {stat.detail}
        </p>
      )}
    </div>
  )
}
