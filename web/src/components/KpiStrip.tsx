import type { KpiData } from '../api'

interface Props {
  kpis: KpiData
}

function parseFrac(s: string): [number, number] | null {
  const m = s.match(/^(\d+) of (\d+)$/)
  return m ? [parseInt(m[1]), parseInt(m[2])] : null
}

interface Tile {
  label: string
  raw: string | number
  accent?: boolean
  warn?: boolean
}

export function KpiStrip({ kpis }: Props) {
  const tiles: Tile[] = [
    { label: 'Roles Processed', raw: kpis.total },
    { label: 'Bias Flagged', raw: kpis.flagged_for_review, warn: true },
    { label: 'Leveling Flags', raw: kpis.leveling_flags, warn: true },
    { label: 'Pay Range', raw: kpis.with_pay_range },
    { label: 'Quotes Verified', raw: kpis.verified, accent: true },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {tiles.map((t) => {
        const frac = typeof t.raw === 'string' ? parseFrac(t.raw) : null
        const pct = frac ? Math.round((frac[0] / Math.max(frac[1], 1)) * 100) : null
        const displayValue = typeof t.raw === 'number' ? t.raw : frac ? frac[0] : t.raw

        return (
          <div
            key={t.label}
            className={`rounded-xl border p-4 flex flex-col gap-1 ${
              t.accent ? 'border-emerald-200 bg-emerald-50/40' : 'border-border bg-card'
            }`}
          >
            <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              {t.label}
            </p>
            <p className={`text-2xl font-bold tabular-nums leading-none mt-0.5 ${
              t.accent ? 'text-emerald-700' : 'text-foreground'
            }`}>
              {displayValue}
            </p>
            {frac && pct !== null && (
              <div className="mt-1.5">
                <div className="h-1 rounded-full bg-muted/80 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: t.accent ? '#10b981'
                        : t.warn && pct > 25 ? '#f97316'
                        : '#3b82f6',
                    }}
                  />
                </div>
                <p className="text-[10px] text-muted-foreground mt-0.5">{pct}% of {frac[1]}</p>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
