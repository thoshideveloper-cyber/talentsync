import { useMemo } from 'react'
import { DonutChart } from './DonutChart'
import type { SkillFreq, JobRecord } from '../api'

interface Props {
  skills: SkillFreq[]
  total: number
  records: JobRecord[]
}

const SENIORITY_COLORS: Record<string, string> = {
  'Executive':  '#7c3aed',
  'Senior':     '#4f46e5',
  'Mid-Level':  '#2563eb',
  'Entry-Level':'#0891b2',
  'Internship': '#0d9488',
  'Uncertain':  '#d97706',
}

const LEVEL_ORDER = ['Executive', 'Senior', 'Mid-Level', 'Entry-Level', 'Internship', 'Uncertain']

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-border bg-card ${className}`}>
      {children}
    </div>
  )
}

function SectionTitle({ title, caption }: { title: string; caption?: string }) {
  return (
    <div className="mb-5">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {caption && <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">{caption}</p>}
    </div>
  )
}

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold tabular-nums text-foreground leading-none">{value}</p>
      {sub && <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  )
}

export function SkillsView({ skills, total, records }: Props) {
  if (skills.length === 0 && records.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-16 text-center space-y-2">
        <p className="text-sm font-semibold text-foreground">Nothing to analyse yet</p>
        <p className="text-sm text-muted-foreground">Add your first JD in the Workspace and check back here.</p>
      </div>
    )
  }

  const max = skills[0]?.count ?? 1

  // ── KPI computations ───────────────────────────────────────────────────────
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

  // ── Seniority distribution ─────────────────────────────────────────────────
  const seniorityDist: Record<string, number> = {}
  records.forEach(r => { seniorityDist[r.ai_seniority] = (seniorityDist[r.ai_seniority] ?? 0) + 1 })
  const senioritySegments = LEVEL_ORDER
    .filter(l => seniorityDist[l])
    .map(l => ({ label: l, value: seniorityDist[l], color: SENIORITY_COLORS[l] ?? '#94a3b8' }))

  // ── Status distribution ────────────────────────────────────────────────────
  const statusDist: Record<string, number> = {}
  records.forEach(r => { statusDist[r.status] = (statusDist[r.status] ?? 0) + 1 })
  const statusColors: Record<string, string> = { ok: '#10b981', unverified: '#f59e0b', failed: '#ef4444' }
  const statusSegments = Object.entries(statusDist)
    .map(([label, value]) => ({ label, value, color: statusColors[label] ?? '#94a3b8' }))
    .sort((a, b) => b.value - a.value)

  // ── Flag analysis ──────────────────────────────────────────────────────────
  const flagRows = [
    { label: 'Bias language',   count: records.filter(r => r.bias_flags.length > 0).length, color: '#f97316' },
    { label: 'Level mismatch',  count: records.filter(r => r.audit_mismatch).length,         color: '#ef4444' },
    { label: 'No pay range',    count: records.filter(r => !r.pay_range_present).length,     color: '#eab308' },
    { label: 'Unverified',      count: records.filter(r => !r.is_verified).length,           color: '#94a3b8' },
  ]

  // ── Score buckets ─────────────────────────────────────────────────────────
  const scoreBuckets = [
    { range: '0–20',   color: '#ef4444', count: 0 },
    { range: '21–40',  color: '#f97316', count: 0 },
    { range: '41–60',  color: '#eab308', count: 0 },
    { range: '61–80',  color: '#3b82f6', count: 0 },
    { range: '81–100', color: '#10b981', count: 0 },
  ]
  records.forEach(r => {
    const i = r.quality_score <= 20 ? 0 : r.quality_score <= 40 ? 1 : r.quality_score <= 60 ? 2 : r.quality_score <= 80 ? 3 : 4
    scoreBuckets[i].count++
  })
  const maxBucket = Math.max(...scoreBuckets.map(b => b.count), 1)

  // ── Skills by level ────────────────────────────────────────────────────────
  const skillsByLevel: Record<string, { count: number; topSkills: string[] }> = {}
  LEVEL_ORDER.forEach(level => {
    const lr = records.filter(r => r.ai_seniority === level)
    if (!lr.length) return
    const sm: Record<string, number> = {}
    lr.forEach(r => r.required_skills.forEach(s => { sm[s] = (sm[s] ?? 0) + 1 }))
    skillsByLevel[level] = {
      count: lr.length,
      topSkills: Object.entries(sm).sort(([, a], [, b]) => b - a).slice(0, 4).map(([s]) => s),
    }
  })

  // ── Skill co-occurrence ───────────────────────────────────────────────────
  const pairCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    records.forEach(r => {
      const s = r.required_skills
      for (let i = 0; i < s.length; i++)
        for (let j = i + 1; j < s.length; j++) {
          const key = [s[i], s[j]].sort().join(' + ')
          counts[key] = (counts[key] ?? 0) + 1
        }
    })
    return Object.entries(counts).filter(([, c]) => c >= 2).sort(([, a], [, b]) => b - a).slice(0, 8)
  }, [records])

  // ── Compliance by seniority ───────────────────────────────────────────────
  const complianceByLevel = useMemo(() =>
    LEVEL_ORDER.filter(l => seniorityDist[l]).map(level => {
      const lr = records.filter(r => r.ai_seniority === level)
      const flagged = lr.filter(r => r.compliance_verdict === 'warn').length
      return { level, total: lr.length, flagged, pct: Math.round((flagged / lr.length) * 100) }
    }),
  [records, seniorityDist])

  // ── Headline insights ─────────────────────────────────────────────────────
  const missingPay = records.filter(r => !r.pay_range_present).length
  const topSkill = skills[0]?.skill ?? null
  const headlineInsights: string[] = []
  if (topSkill && topSkillCoverage > 0)
    headlineInsights.push(`"${topSkill}" appears in ${topSkillCoverage}% of roles — your highest-demand skill.`)
  if (missingPay > 0)
    headlineInsights.push(`${missingPay} role${missingPay !== 1 ? 's' : ''} missing pay range — add one to improve candidate conversion.`)
  const worstFlag = [...complianceByLevel].sort((a, b) => b.pct - a.pct)[0]
  if (worstFlag?.pct > 0)
    headlineInsights.push(`${worstFlag.level} roles have the highest compliance flag rate at ${worstFlag.pct}%.`)

  return (
    <div className="space-y-5">

      {/* ── Headline insight digest ───────────────────────────────────────── */}
      {headlineInsights.length > 0 && (
        <div className="rounded-xl border border-border bg-card px-5 py-4 space-y-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Key takeaways
          </p>
          {headlineInsights.map((insight, i) => (
            <div key={i} className="flex items-start gap-3">
              <span className="mt-2 h-1 w-1 rounded-full bg-foreground/30 shrink-0" />
              <p className="text-sm text-foreground leading-relaxed">{insight}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── KPI row ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Unique Skills',     value: skills.length,         sub: `across ${total} role${total !== 1 ? 's' : ''}` },
          { label: 'Avg Skills / Role', value: avgSkillsPerRole,       sub: 'required per JD' },
          { label: 'Roles 3+ Skills',   value: rolesWithThreePlus,     sub: `${Math.round((rolesWithThreePlus / Math.max(total, 1)) * 100)}% of total` },
          { label: 'Avg Quality',       value: `${avgScore}/100`,      sub: avgScore >= 70 ? 'Strong' : avgScore >= 50 ? 'Average' : 'Needs work' },
        ].map(k => (
          <Card key={k.label} className="p-4">
            <Stat label={k.label} value={k.value} sub={k.sub} />
          </Card>
        ))}
      </div>

      {/* ── Charts row ────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Seniority donut */}
        <Card className="p-5">
          <SectionTitle title="Seniority Mix" caption="Distribution of open roles across levels." />
          <div className="flex items-center gap-5">
            <DonutChart segments={senioritySegments} centerLabel="roles" size={88} />
            <div className="flex-1 space-y-2 min-w-0">
              {senioritySegments.map(s => (
                <div key={s.label} className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                    <span className="text-xs text-foreground truncate">{s.label}</span>
                  </div>
                  <span className="text-xs font-semibold tabular-nums text-foreground">{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Role quality donut */}
        <Card className="p-5">
          <SectionTitle title="Role Quality" caption="Verification status — 'ok' means seniority matched a quote." />
          <div className="flex items-center gap-5">
            <DonutChart segments={statusSegments} centerLabel="roles" size={88} />
            <div className="flex-1 space-y-2">
              {statusSegments.map(s => (
                <div key={s.label} className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                    <span className="text-xs capitalize text-foreground">{s.label}</span>
                  </div>
                  <span className="text-xs font-semibold tabular-nums text-foreground">{s.value}</span>
                </div>
              ))}
              <div className="pt-2 border-t border-border/60">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Avg score</span>
                  <span className="text-xs font-bold tabular-nums text-foreground">
                    {avgScore}<span className="text-muted-foreground font-normal">/100</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Flag analysis */}
        <Card className="p-5">
          <SectionTitle title="Flag Analysis" caption="Roles carrying each type of issue." />
          <div className="space-y-3.5">
            {flagRows.map(f => {
              const pct = total > 0 ? (f.count / total) * 100 : 0
              return (
                <div key={f.label}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-foreground">{f.label}</span>
                    <span className="text-xs tabular-nums text-muted-foreground">
                      {f.count}<span className="text-muted-foreground/60"> / {total}</span>
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, backgroundColor: f.color }} />
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      {/* ── Skill demand frequency ────────────────────────────────────────── */}
      <Card className="p-5">
        <SectionTitle
          title="Skill Demand"
          caption={`How often each skill appears across your ${total} role${total !== 1 ? 's' : ''}.`}
        />
        {skills.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-6">No skills extracted yet.</p>
        ) : (
          <div className="space-y-2">
            {skills.slice(0, 20).map(({ skill, count }, idx) => {
              const pct = (count / max) * 100
              const rolePct = total > 0 ? Math.round((count / total) * 100) : 0
              return (
                <div key={skill} className="flex items-center gap-3">
                  <span className={`w-28 shrink-0 text-xs text-right truncate ${idx < 3 ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>
                    {skill}
                  </span>
                  <div className="flex-1 rounded-full bg-muted h-1.5 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: idx === 0 ? '#2563eb' : idx < 3 ? '#3b82f6' : '#93c5fd',
                      }}
                    />
                  </div>
                  <div className="w-14 shrink-0 text-right">
                    <span className="text-xs font-semibold text-foreground">{rolePct}%</span>
                    <span className="text-xs text-muted-foreground"> ({count})</span>
                  </div>
                </div>
              )
            })}
            {skills.length > 20 && (
              <p className="text-xs text-muted-foreground text-center pt-1">+{skills.length - 20} more skills</p>
            )}
          </div>
        )}
      </Card>

      {/* ── Co-occurrence + Compliance by level ──────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-5">
          <SectionTitle
            title="Commonly Paired Skills"
            caption="Skills that appear together — natural role archetypes in your hiring."
          />
          {pairCounts.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">Add more roles to see pairing patterns.</p>
          ) : (
            <div className="space-y-2">
              {pairCounts.map(([pair, count]) => {
                const pct = (count / (pairCounts[0]?.[1] ?? 1)) * 100
                return (
                  <div key={pair} className="flex items-center gap-3">
                    <span className="w-36 shrink-0 text-xs text-muted-foreground truncate" title={pair}>{pair}</span>
                    <div className="flex-1 rounded-full bg-muted h-1.5 overflow-hidden">
                      <div className="h-full rounded-full bg-violet-400 transition-all duration-500" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs font-semibold tabular-nums text-foreground w-5 text-right shrink-0">{count}</span>
                  </div>
                )
              })}
            </div>
          )}
        </Card>

        <Card className="p-5">
          <SectionTitle
            title="Compliance Flags by Level"
            caption="Which seniority tiers carry the most warnings."
          />
          {complianceByLevel.filter(r => r.total > 0).length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No level data yet.</p>
          ) : (
            <div className="space-y-3.5">
              {complianceByLevel.filter(r => r.total > 0).map(({ level, total: lt, flagged, pct }) => (
                <div key={level}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: SENIORITY_COLORS[level] ?? '#94a3b8' }} />
                      <span className="text-xs text-foreground">{level}</span>
                    </div>
                    <span className="text-xs tabular-nums">
                      <span className="text-muted-foreground">{flagged}/{lt} · </span>
                      <span className={`font-semibold ${pct > 50 ? 'text-red-600' : pct > 25 ? 'text-amber-600' : 'text-emerald-600'}`}>
                        {pct}%
                      </span>
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, backgroundColor: pct > 50 ? '#ef4444' : pct > 25 ? '#f59e0b' : '#10b981' }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ── Skills by level + Score histogram ────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-5">
          <SectionTitle
            title="Skills by Seniority"
            caption="Top skills demanded at each level."
          />
          {Object.keys(skillsByLevel).length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No level data yet.</p>
          ) : (
            <div className="space-y-3">
              {LEVEL_ORDER.filter(l => skillsByLevel[l]).map(level => {
                const { count, topSkills } = skillsByLevel[level]
                return (
                  <div key={level} className="flex items-start gap-3">
                    <div className="flex items-center gap-2 w-24 shrink-0 pt-0.5">
                      <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: SENIORITY_COLORS[level] ?? '#94a3b8' }} />
                      <span className="text-xs font-medium text-foreground truncate">{level}</span>
                    </div>
                    <div className="flex-1 flex flex-wrap gap-1">
                      {topSkills.map(s => (
                        <span key={s} className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] text-foreground">
                          {s}
                        </span>
                      ))}
                    </div>
                    <span className="text-xs tabular-nums text-muted-foreground shrink-0 pt-0.5">{count}</span>
                  </div>
                )
              })}
            </div>
          )}
        </Card>

        <Card className="p-5">
          <SectionTitle
            title="Score Distribution"
            caption="Quality score clusters — below 60 should be enriched before posting."
          />
          {records.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No records yet.</p>
          ) : (
            <div className="flex items-end gap-2.5" style={{ height: '110px' }}>
              {scoreBuckets.map(b => (
                <div key={b.range} className="flex-1 flex flex-col items-center gap-1.5">
                  <span className="text-xs font-bold tabular-nums text-foreground leading-none min-h-[1rem]">
                    {b.count > 0 ? b.count : ''}
                  </span>
                  <div
                    className="w-full rounded-t-md transition-all duration-500"
                    style={{
                      height: b.count > 0 ? `${Math.max((b.count / maxBucket) * 68, 6)}px` : '3px',
                      backgroundColor: b.count > 0 ? b.color : 'hsl(var(--muted))',
                      opacity: b.count > 0 ? 1 : 0.4,
                    }}
                  />
                  <span className="text-[10px] text-muted-foreground text-center leading-tight">{b.range}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

    </div>
  )
}
