import { useEffect, useState } from 'react'
import { api } from '../api'
import type { PostureData } from '../api'
import { ruleLabel } from '../lib/ruleLabels'

export function DashboardView() {
  const [data, setData] = useState<PostureData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true); setError(null)
    try {
      setData(await api.dashboardPosture())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load posture')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-muted-foreground text-sm">
      <span className="inline-block w-4 h-4 border-2 border-muted border-t-primary rounded-full animate-spin mr-2" />
      Loading posture…
    </div>
  )

  if (error) return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {error}
      <button onClick={() => void load()} className="ml-3 underline text-xs">Retry</button>
    </div>
  )

  if (!data) return null

  const passPercent = Math.round(data.overall_pass_rate * 100)

  return (
    <div className="space-y-8">
      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {/* Pass rate ring */}
        <div className="rounded-xl border border-border bg-card p-5 flex flex-col items-center justify-center gap-2">
          <div className="relative h-20 w-20">
            <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90">
              <circle cx="18" cy="18" r="15.9" fill="none" stroke="hsl(var(--muted))" strokeWidth="3" />
              <circle
                cx="18" cy="18" r="15.9"
                fill="none"
                stroke={passPercent >= 80 ? 'hsl(142 76% 36%)' : passPercent >= 50 ? 'hsl(38 92% 50%)' : 'hsl(0 84% 60%)'}
                strokeWidth="3"
                strokeDasharray={`${passPercent} ${100 - passPercent}`}
                strokeLinecap="round"
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-foreground">
              {passPercent}%
            </span>
          </div>
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Pass Rate</span>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 flex flex-col justify-center gap-1">
          <span className="text-3xl font-bold text-foreground">{data.total_versions_checked}</span>
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Versions Checked
          </span>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 flex flex-col justify-center gap-1">
          <span className="text-3xl font-bold text-foreground">{data.top_rules.length}</span>
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Unique Rules Triggered
          </span>
        </div>
      </div>

      {/* Top rules */}
      {data.top_rules.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-bold text-foreground mb-4">Top Triggered Rules</h3>
          <div className="space-y-2">
            {data.top_rules.map((rule, i) => {
              const maxCount = data.top_rules[0]?.count ?? 1
              const pct = Math.round((rule.count / maxCount) * 100)
              return (
                <div key={rule.rule_id} className="flex items-center gap-3">
                  <span className="text-xs font-medium text-muted-foreground w-5 text-right">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-foreground truncate" title={rule.rule_id}>{ruleLabel(rule.rule_id)}</span>
                      <span className="text-xs text-muted-foreground ml-2 flex-shrink-0">{rule.count}×</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 8-week trend */}
      <div className="rounded-xl border border-border bg-card p-5">
        <h3 className="text-sm font-bold text-foreground mb-4">8-Week Pass Rate Trend</h3>
        {data.trend.every(t => t.pass_rate === null) ? (
          <p className="text-xs text-muted-foreground">No data yet for this period.</p>
        ) : (
          <div className="flex items-end gap-1.5 h-24">
            {data.trend.map(entry => {
              const pct = entry.pass_rate !== null ? Math.round(entry.pass_rate * 100) : null
              const barH = pct !== null ? `${Math.max(4, pct)}%` : '4%'
              const barColor = pct === null ? 'bg-muted' :
                pct >= 80 ? 'bg-emerald-500' :
                pct >= 50 ? 'bg-amber-400' : 'bg-red-400'
              return (
                <div key={entry.week} className="flex-1 flex flex-col items-center gap-1 group relative">
                  <div className="w-full flex flex-col-reverse h-20">
                    <div
                      className={`w-full rounded-t transition-all ${barColor}`}
                      style={{ height: barH }}
                      title={pct !== null ? `${entry.week}: ${pct}%` : `${entry.week}: no data`}
                    />
                  </div>
                  <span className="text-[9px] text-muted-foreground rotate-45 origin-left hidden sm:block" style={{ fontSize: '8px' }}>
                    {entry.week.replace(/^\d{4}-/, '')}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Recent overrides */}
      {data.recent_overrides.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-bold text-foreground mb-4">Recent Compliance Overrides</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left font-semibold text-muted-foreground pb-2 pr-4">Actor</th>
                  <th className="text-left font-semibold text-muted-foreground pb-2 pr-4">Action</th>
                  <th className="text-left font-semibold text-muted-foreground pb-2">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.recent_overrides.map((ov, i) => (
                  <tr key={i}>
                    <td className="py-2 pr-4 font-medium text-foreground">{ov.actor_email}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{ov.action}</td>
                    <td className="py-2 text-muted-foreground">
                      {ov.ts ? new Date(ov.ts).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data.recent_overrides.length === 0 && (
        <div className="rounded-xl border border-border bg-muted/30 px-5 py-8 text-center">
          <p className="text-xs text-muted-foreground">No compliance overrides recorded yet.</p>
        </div>
      )}

      <div className="text-right">
        <button
          onClick={() => void load()}
          className="text-xs text-primary hover:underline"
        >
          Refresh
        </button>
      </div>
    </div>
  )
}
