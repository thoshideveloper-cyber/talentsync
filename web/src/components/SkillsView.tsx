import { DonutChart } from './DonutChart'
import type { SkillFreq, JobRecord } from '../api'

interface Props {
  skills: SkillFreq[]
  total: number
  records: JobRecord[]
}

const SENIORITY_COLORS: Record<string, string> = {
  'Executive': '#9333ea',
  'Senior': '#7c3aed',
  'Mid-Level': '#2563eb',
  'Entry-Level': '#059669',
  'Internship': '#0d9488',
  'Uncertain': '#d97706',
}

const LEVEL_ORDER = ['Executive', 'Senior', 'Mid-Level', 'Entry-Level', 'Internship', 'Uncertain']

function KpiTile({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl border p-4 flex flex-col gap-1 ${accent ? 'border-blue-200 bg-blue-50/40' : 'border-border bg-card'}`}>
      <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</p>
      <p className={`text-2xl font-bold tabular-nums leading-none mt-0.5 ${accent ? 'text-blue-700' : 'text-foreground'}`}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  )
}

export function SkillsView({ skills, total, records }: Props) {
  if (skills.length === 0 && records.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-16 text-center text-sm text-muted-foreground">
        No data yet. Process a job description to see analytics.
      </div>
    )
  }

  const max = skills[0]?.count ?? 1

  // KPI computations
  const avgSkillsPerRole = records.length > 0
    ? (records.reduce((s, r) => s + r.required_skills.length, 0) / records.length).toFixed(1)
    : '—'
  const rolesWithThreePlus = records.filter(r => r.required_skills.length >= 3).length
  const topSkillCoverage = records.length > 0 && skills.length > 0
    ? Math.round((skills[0].count / records.length) * 100)
    : 0
  const avgScore = records.length > 0
    ? Math.round(records.reduce((s, r) => s + r.quality_score, 0) / records.length)
    : 0

  // Seniority distribution for donut
  const seniorityDist: Record<string, number> = {}
  records.forEach(r => { seniorityDist[r.ai_seniority] = (seniorityDist[r.ai_seniority] ?? 0) + 1 })
  const senioritySegments = LEVEL_ORDER
    .filter(l => seniorityDist[l])
    .map(l => ({ label: l, value: seniorityDist[l], color: SENIORITY_COLORS[l] ?? '#94a3b8' }))

  // Status distribution for donut
  const statusDist: Record<string, number> = {}
  records.forEach(r => { statusDist[r.status] = (statusDist[r.status] ?? 0) + 1 })
  const statusColors: Record<string, string> = { ok: '#10b981', unverified: '#f59e0b', failed: '#ef4444' }
  const statusSegments = Object.entries(statusDist)
    .map(([label, value]) => ({ label, value, color: statusColors[label] ?? '#94a3b8' }))
    .sort((a, b) => b.value - a.value)

  // Flag analysis
  const flagRows = [
    { label: 'Bias language', count: records.filter(r => r.bias_flags.length > 0).length, color: '#f97316' },
    { label: 'Level mismatch', count: records.filter(r => r.audit_mismatch).length, color: '#ef4444' },
    { label: 'No pay range', count: records.filter(r => !r.pay_range_present).length, color: '#eab308' },
    { label: 'Unverified', count: records.filter(r => !r.is_verified).length, color: '#94a3b8' },
  ]

  // Score distribution
  const scoreBuckets = [
    { range: '0–20', color: '#ef4444', count: 0 },
    { range: '21–40', color: '#f97316', count: 0 },
    { range: '41–60', color: '#eab308', count: 0 },
    { range: '61–80', color: '#3b82f6', count: 0 },
    { range: '81–100', color: '#10b981', count: 0 },
  ]
  records.forEach(r => {
    const idx = r.quality_score <= 20 ? 0 : r.quality_score <= 40 ? 1 : r.quality_score <= 60 ? 2 : r.quality_score <= 80 ? 3 : 4
    scoreBuckets[idx].count++
  })
  const maxBucket = Math.max(...scoreBuckets.map(b => b.count), 1)

  // Skills by seniority level
  const skillsByLevel: Record<string, { count: number; topSkills: string[] }> = {}
  LEVEL_ORDER.forEach(level => {
    const lr = records.filter(r => r.ai_seniority === level)
    if (lr.length === 0) return
    const sm: Record<string, number> = {}
    lr.forEach(r => r.required_skills.forEach(s => { sm[s] = (sm[s] ?? 0) + 1 }))
    skillsByLevel[level] = {
      count: lr.length,
      topSkills: Object.entries(sm).sort(([, a], [, b]) => b - a).slice(0, 4).map(([s]) => s),
    }
  })

  return (
    <div className="space-y-5">
      {/* KPI tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiTile label="Unique Skills" value={skills.length} sub={`across ${total} role${total !== 1 ? 's' : ''}`} accent />
        <KpiTile label="Avg Skills / Role" value={avgSkillsPerRole} sub="required per JD" />
        <KpiTile label="Roles with 3+ Skills" value={rolesWithThreePlus} sub={`${Math.round((rolesWithThreePlus / Math.max(total, 1)) * 100)}% of total`} />
        <KpiTile label="Top Skill Coverage" value={`${topSkillCoverage}%`} sub={skills[0]?.skill ?? '—'} />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Seniority donut */}
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-4">Seniority Mix</p>
          <div className="flex items-center gap-4">
            <DonutChart segments={senioritySegments} centerLabel="roles" size={96} />
            <div className="flex-1 space-y-1.5 min-w-0">
              {senioritySegments.map(s => (
                <div key={s.label} className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                    <span className="text-xs text-foreground truncate">{s.label}</span>
                  </div>
                  <span className="text-xs font-bold tabular-nums shrink-0">{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Quality donut */}
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-4">Role Quality</p>
          <div className="flex items-center gap-4">
            <DonutChart segments={statusSegments} centerLabel="roles" size={96} />
            <div className="flex-1 space-y-1.5">
              {statusSegments.map(s => (
                <div key={s.label} className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                    <span className="text-xs capitalize text-foreground">{s.label}</span>
                  </div>
                  <span className="text-xs font-bold tabular-nums">{s.value}</span>
                </div>
              ))}
              <div className="pt-1.5 border-t border-border">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Avg score</span>
                  <span className="text-xs font-bold tabular-nums">{avgScore}<span className="text-muted-foreground font-normal">/100</span></span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Flag analysis */}
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-4">Flag Analysis</p>
          <div className="space-y-3">
            {flagRows.map(f => {
              const pct = total > 0 ? (f.count / total) * 100 : 0
              return (
                <div key={f.label}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-muted-foreground">{f.label}</span>
                    <span className="text-xs font-semibold tabular-nums">
                      {f.count}
                      <span className="text-muted-foreground font-normal"> / {total}</span>
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${pct}%`, backgroundColor: f.color, transition: 'width 0.5s ease' }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Skill demand frequency */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Skill Demand Frequency</p>
          <span className="text-xs text-muted-foreground">{skills.length} unique · {total} roles</span>
        </div>
        {skills.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-6">No skills extracted yet.</p>
        ) : (
          <div className="space-y-2">
            {skills.slice(0, 20).map(({ skill, count }, idx) => {
              const pct = (count / max) * 100
              const rolePct = total > 0 ? Math.round((count / total) * 100) : 0
              const isTop = idx === 0
              const isHighlight = idx < 3
              return (
                <div key={skill} className="flex items-center gap-3">
                  <span className={`w-28 shrink-0 text-xs text-right ${isHighlight ? 'font-semibold text-foreground' : 'text-muted-foreground'}`}>
                    {skill}
                  </span>
                  <div className="flex-1 rounded-full bg-muted h-1.5 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: isTop ? '#2563eb' : isHighlight ? '#3b82f6' : '#93c5fd',
                        transition: 'width 0.5s ease',
                      }}
                    />
                  </div>
                  <div className="w-16 shrink-0 text-right">
                    <span className="text-xs font-semibold text-foreground">{rolePct}%</span>
                    <span className="text-xs text-muted-foreground"> ({count})</span>
                  </div>
                </div>
              )
            })}
            {skills.length > 20 && (
              <p className="text-xs text-muted-foreground text-center pt-1">+{skills.length - 20} additional skills</p>
            )}
          </div>
        )}
      </div>

      {/* Bottom: Skills by level + Score distribution */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Skills by seniority */}
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-4">Skills by Seniority</p>
          {Object.keys(skillsByLevel).length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No level data yet.</p>
          ) : (
            <div className="space-y-3">
              {LEVEL_ORDER.filter(l => skillsByLevel[l]).map(level => {
                const { count, topSkills } = skillsByLevel[level]
                return (
                  <div key={level} className="flex items-start gap-3">
                    <div className="flex items-center gap-1.5 w-24 shrink-0 pt-0.5">
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: SENIORITY_COLORS[level] ?? '#94a3b8' }} />
                      <span className="text-xs font-medium text-foreground truncate">{level}</span>
                    </div>
                    <div className="flex-1 flex flex-wrap gap-1">
                      {topSkills.map(s => (
                        <span key={s} className="rounded-md border border-border bg-muted/50 px-1.5 py-0.5 text-[10px] text-foreground">
                          {s}
                        </span>
                      ))}
                      {topSkills.length === 0 && <span className="text-xs text-muted-foreground">—</span>}
                    </div>
                    <span className="text-xs tabular-nums text-muted-foreground shrink-0 pt-0.5">{count}</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Score histogram */}
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-4">Score Distribution</p>
          {records.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No records yet.</p>
          ) : (
            <div className="flex items-end gap-2" style={{ height: '88px' }}>
              {scoreBuckets.map(b => (
                <div key={b.range} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-[10px] font-bold tabular-nums text-foreground leading-none">
                    {b.count > 0 ? b.count : ''}
                  </span>
                  <div
                    className="w-full rounded-t-sm"
                    style={{
                      height: b.count > 0 ? `${Math.max((b.count / maxBucket) * 58, 4)}px` : '2px',
                      backgroundColor: b.count > 0 ? b.color : '#e2e8f0',
                      transition: 'height 0.5s ease',
                    }}
                  />
                  <span className="text-[10px] text-muted-foreground text-center leading-tight">{b.range}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
