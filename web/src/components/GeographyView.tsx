import { useMemo } from 'react'
import type { JobRecord } from '../api'

const HUBS: { label: string; patterns: RegExp[] }[] = [
  { label: 'Delhi NCR',  patterns: [/delhi\s*ncr/i, /\bncr\b/i, /\bgurugram\b/i, /\bgurgaon\b/i, /\bnoida\b/i, /\bnew delhi\b/i, /\bdelhi\b/i] },
  { label: 'Bengaluru',  patterns: [/bengaluru/i, /bangalore/i] },
  { label: 'Mumbai',     patterns: [/mumbai/i, /\bbombay\b/i, /navi mumbai/i] },
  { label: 'Hyderabad',  patterns: [/hyderabad/i] },
  { label: 'Pune',       patterns: [/\bpune\b/i] },
  { label: 'Chennai',    patterns: [/chennai/i, /\bmadras\b/i] },
  { label: 'Kolkata',    patterns: [/kolkata/i, /calcutta/i] },
  { label: 'Ahmedabad',  patterns: [/ahmedabad/i] },
  { label: 'Jaipur',     patterns: [/jaipur/i] },
  { label: 'Kochi',      patterns: [/kochi/i, /cochin/i] },
]

const WORK_MODELS: { label: string; patterns: RegExp[]; color: string }[] = [
  { label: 'Remote',  patterns: [/\bremote\b/i, /work from home/i, /\bwfh\b/i],                      color: '#10b981' },
  { label: 'Hybrid',  patterns: [/\bhybrid\b/i],                                                      color: '#3b82f6' },
  { label: 'On-site', patterns: [/on[\s-]?site/i, /in[\s-]?office/i, /work from office/i],           color: '#f59e0b' },
]

const MODEL_COLORS: Record<string, string> = Object.fromEntries(WORK_MODELS.map(m => [m.label, m.color]))

function classify<T extends { label: string; patterns: RegExp[] }>(
  text: string, groups: T[], fallback: string,
): string {
  for (const g of groups)
    if (g.patterns.some(p => p.test(text))) return g.label
  return fallback
}

function tally(records: JobRecord[], pick: (r: JobRecord) => string) {
  const freq = new Map<string, number>()
  for (const r of records) {
    const key = pick(r)
    freq.set(key, (freq.get(key) ?? 0) + 1)
  }
  return [...freq.entries()].map(([label, count]) => ({ label, count })).sort((a, b) => b.count - a.count)
}

function BarList({
  title,
  caption,
  rows,
  colorMap,
}: {
  title: string
  caption: string
  rows: { label: string; count: number }[]
  colorMap?: Record<string, string>
}) {
  const max = rows[0]?.count ?? 1
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-5">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">{caption}</p>
      </div>
      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">No data yet.</p>
      ) : (
        <div className="space-y-3">
          {rows.map(row => {
            const pct = Math.round((row.count / max) * 100)
            const color = colorMap?.[row.label] ?? 'hsl(var(--primary))'
            return (
              <div key={row.label}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-medium text-foreground">{row.label}</span>
                  <span className="text-xs tabular-nums text-muted-foreground">{row.count} role{row.count !== 1 ? 's' : ''}</span>
                </div>
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${pct}%`, backgroundColor: color }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function GeographyView({ records }: { records: JobRecord[] }) {
  const { locations, models } = useMemo(() => ({
    locations: tally(records, r => classify(r.raw_jd ?? '', HUBS, 'Unspecified')),
    models:    tally(records, r => classify(r.raw_jd ?? '', WORK_MODELS, 'Unspecified')),
  }), [records])

  if (records.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border px-6 py-16 text-center">
        <p className="text-sm font-semibold text-foreground">No roles yet</p>
        <p className="mt-1 text-sm text-muted-foreground">Add a JD to see the location breakdown.</p>
      </div>
    )
  }

  const topCity   = locations.find(l => l.label !== 'Unspecified')
  const topModel  = models.find(m => m.label !== 'Unspecified')
  const total     = records.length

  return (
    <div className="space-y-5">

      {/* ── Quick summary ───────────────────────────────────────────────── */}
      {(topCity || topModel) && (
        <div className="rounded-xl border border-border bg-card px-5 py-4 flex flex-wrap gap-6">
          {topCity && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Top city</p>
              <p className="mt-1 text-sm font-semibold text-foreground">
                {topCity.label}
                <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                  {Math.round((topCity.count / total) * 100)}% of roles
                </span>
              </p>
            </div>
          )}
          {topCity && topModel && <div className="h-8 w-px bg-border self-center" />}
          {topModel && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Top work model</p>
              <p className="mt-1 text-sm font-semibold text-foreground">
                {topModel.label}
                <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                  {Math.round((topModel.count / total) * 100)}% of roles
                </span>
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── Charts ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <BarList
          title="Roles by location"
          caption="Parsed from JD text against major Indian hiring hubs."
          rows={locations}
        />
        <BarList
          title="Roles by work model"
          caption="Remote, hybrid, or on-site — extracted from JD text."
          rows={models}
          colorMap={MODEL_COLORS}
        />
      </div>

      <p className="text-xs text-muted-foreground">
        Location and work model are inferred from JD text — not a verified address field.
      </p>
    </div>
  )
}
