import { useState } from 'react'
import type { JobRecord } from '../api'
import { api } from '../api'

interface Props {
  records: JobRecord[]
}

type SortKey = 'role' | 'ai_seniority' | 'quality_score' | 'status'

const LEVEL_COLORS: Record<string, string> = {
  'Senior': 'bg-violet-100 text-violet-800',
  'Executive': 'bg-purple-100 text-purple-800',
  'Mid-Level': 'bg-blue-100 text-blue-800',
  'Entry-Level': 'bg-emerald-100 text-emerald-800',
  'Internship': 'bg-teal-100 text-teal-800',
  'Uncertain': 'bg-amber-100 text-amber-800',
}

export function Board({ records }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('quality_score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [selected, setSelected] = useState<JobRecord | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const toggleExpand = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const sorted = [...records].sort((a, b) => {
    let av: string | number = a[sortKey] ?? ''
    let bv: string | number = b[sortKey] ?? ''
    if (typeof av === 'number' && typeof bv === 'number') {
      return sortDir === 'asc' ? av - bv : bv - av
    }
    av = String(av).toLowerCase()
    bv = String(bv).toLowerCase()
    return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
  })

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const Th = ({ col, label }: { col: SortKey; label: string }) => (
    <th
      className="px-3 py-2.5 text-left text-[10px] font-semibold uppercase tracking-widest text-muted-foreground cursor-pointer hover:text-foreground select-none"
      onClick={() => toggleSort(col)}
    >
      {label} {sortKey === col ? (sortDir === 'asc' ? '↑' : '↓') : ''}
    </th>
  )

  const handleDownload = (rec: JobRecord) => {
    window.open(api.docxUrl(rec.id), '_blank')
  }

  if (records.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-12 text-center text-muted-foreground text-sm">
        No records yet. Paste a JD above to process your first one.
      </div>
    )
  }

  const avgScore = Math.round(records.reduce((s, r) => s + r.quality_score, 0) / records.length)
  const statusCounts: Record<string, number> = {}
  records.forEach(r => { statusCounts[r.status] = (statusCounts[r.status] ?? 0) + 1 })
  const flaggedCount = records.filter(r => r.bias_flags.length > 0 || r.audit_mismatch).length
  const verifiedCount = records.filter(r => r.is_verified).length
  const statusConfig: Record<string, string> = {
    ok: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    unverified: 'bg-amber-50 text-amber-700 border-amber-200',
    failed: 'bg-red-50 text-red-700 border-red-200',
  }

  return (
    <div className="space-y-4">
      {/* Summary analytics strip */}
      <div className="rounded-xl border border-border bg-card p-4 flex flex-wrap items-center gap-5">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Avg Score</p>
          <p className="text-xl font-bold tabular-nums leading-none mt-0.5">
            {avgScore}<span className="text-sm font-normal text-muted-foreground">/100</span>
          </p>
        </div>
        <div className="h-8 w-px bg-border" />
        <div className="flex items-center gap-2 flex-wrap">
          {Object.entries(statusCounts).map(([status, count]) => (
            <span key={status} className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${statusConfig[status] ?? 'bg-muted text-foreground border-border'}`}>
              {count} {status}
            </span>
          ))}
        </div>
        <div className="h-8 w-px bg-border" />
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span><span className="font-semibold text-foreground">{verifiedCount}</span> verified</span>
          <span><span className={`font-semibold ${flaggedCount > 0 ? 'text-orange-600' : 'text-foreground'}`}>{flaggedCount}</span> flagged</span>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-muted/40">
            <tr>
              <Th col="role" label="Role" />
              <Th col="ai_seniority" label="True Level" />
              <th className="px-3 py-2.5 text-left text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Skills
              </th>
              <th className="px-3 py-2.5 text-left text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Flags
              </th>
              <Th col="quality_score" label="Score" />
              <Th col="status" label="Status" />
              <th className="px-3 py-2.5 text-left text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sorted.map((rec) => (
              <>
                <tr
                  key={rec.id}
                  className={`hover:bg-muted/30 cursor-pointer transition-colors ${
                    selected?.id === rec.id ? 'bg-accent/30' : ''
                  }`}
                  onClick={() => setSelected(selected?.id === rec.id ? null : rec)}
                >
                  <td className="px-3 py-3">
                    <div className="font-medium text-foreground">{rec.role}</div>
                    <div className="text-xs text-muted-foreground">{rec.id}</div>
                  </td>
                  <td className="px-3 py-3">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${LEVEL_COLORS[rec.ai_seniority] ?? 'bg-gray-100 text-gray-800'}`}>
                      {rec.ai_seniority}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap gap-1 max-w-xs">
                      {rec.required_skills.slice(0, 4).map((s) => (
                        <span key={s} className="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-700 border border-blue-200">
                          {s}
                        </span>
                      ))}
                      {rec.required_skills.length > 4 && (
                        <span className="text-xs text-muted-foreground">+{rec.required_skills.length - 4}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex gap-1 flex-wrap max-w-[200px]">
                      {rec.audit_mismatch && (
                        <span className="rounded bg-red-50 border border-red-200 px-1.5 py-0.5 text-xs text-red-700">⚑ level mismatch</span>
                      )}
                      {rec.bias_flags.map(flag => (
                        <span key={flag} className="rounded bg-orange-50 border border-orange-200 px-1.5 py-0.5 text-xs text-orange-700">
                          {flag}
                        </span>
                      ))}
                      {!rec.pay_range_present && (
                        <span className="rounded bg-yellow-50 border border-yellow-200 px-1.5 py-0.5 text-xs text-yellow-700">no pay</span>
                      )}
                      {!rec.audit_mismatch && rec.bias_flags.length === 0 && rec.pay_range_present && (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <span className="font-bold tabular-nums">{rec.quality_score}</span>
                    <span className="text-muted-foreground">/100</span>
                  </td>
                  <td className="px-3 py-3">
                    <span className={`text-xs font-medium ${
                      rec.status === 'ok' ? 'text-green-600' :
                      rec.status === 'unverified' ? 'text-amber-600' :
                      'text-red-600'
                    }`}>
                      {rec.status}
                    </span>
                  </td>
                  <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                    <div className="flex gap-1.5">
                      <button
                        onClick={(e) => toggleExpand(rec.id, e)}
                        className={`rounded border px-2 py-1 text-xs transition-colors ${
                          expanded.has(rec.id)
                            ? 'bg-muted border-border text-foreground'
                            : 'hover:bg-muted/50'
                        }`}
                        title="Toggle raw source text"
                      >
                        {expanded.has(rec.id) ? 'Raw ▲' : 'Raw ▼'}
                      </button>
                      <button
                        onClick={() => handleDownload(rec)}
                        className="rounded border px-2 py-1 text-xs hover:bg-muted/50 transition-colors"
                        title="Download corrected .docx"
                      >
                        ⬇ .docx
                      </button>
                    </div>
                  </td>
                </tr>
                {expanded.has(rec.id) && (
                  <tr key={`${rec.id}-raw`} className="bg-muted/20">
                    <td colSpan={7} className="px-4 pb-3 pt-2">
                      <p className="text-xs font-semibold text-muted-foreground mb-1.5">Raw draft (messy input)</p>
                      <pre className="rounded-lg border border-border bg-background p-3 text-xs whitespace-pre-wrap break-words font-mono leading-relaxed max-h-48 overflow-y-auto">
                        {rec.raw_jd}
                      </pre>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold text-lg">{selected.role}</h3>
              <p className="text-sm text-muted-foreground">{selected.id} · {selected.input_format}</p>
            </div>
            <button onClick={() => setSelected(null)} className="text-muted-foreground hover:text-foreground">✕</button>
          </div>

          {/* Grounding quote — R10 */}
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs font-semibold text-muted-foreground mb-1">
              Seniority Evidence {selected.is_verified ? '(Verified ✓)' : '(Unverified ⚠)'}
            </p>
            <blockquote className="text-sm italic">
              {selected.raw_text_justification || '—'}
            </blockquote>
          </div>

          {/* Indicative summary */}
          <div className="rounded-lg border border-dashed border-amber-300 bg-amber-50 p-3">
            <p className="text-xs font-semibold text-amber-700 mb-1">✦ Generated Summary — indicative, not verified</p>
            <p className="text-sm italic text-amber-900">{selected.one_line_summary}</p>
          </div>

          {/* Flagged language */}
          {selected.bias_flags.length > 0 && (
            <div className="rounded-lg border border-orange-200 bg-orange-50 p-3">
              <p className="text-xs font-semibold text-orange-700 mb-2">⚑ Flagged language — review before posting</p>
              <div className="flex flex-wrap gap-1.5">
                {selected.bias_flags.map(flag => (
                  <span key={flag} className="rounded border border-orange-300 bg-white px-2 py-0.5 text-xs font-medium text-orange-800">
                    {flag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Level mismatch */}
          {selected.audit_mismatch && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="text-xs font-semibold text-red-700">⚑ Level mismatch — stated "{selected.native_label}" but text signals "{selected.ai_seniority}"</p>
            </div>
          )}

          {/* Score breakdown */}
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">Score breakdown</p>
            <p className="text-sm">{selected.quality_score}/100 · {selected.score_breakdown.join(' · ')}</p>
          </div>

          {/* Raw JD preview */}
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">Source text</p>
            <pre className="rounded-lg bg-muted/40 p-3 text-xs whitespace-pre-wrap break-words font-mono max-h-40 overflow-y-auto">
              {selected.raw_jd}
            </pre>
          </div>

          <button
            onClick={() => handleDownload(selected)}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            ⬇ Download Corrected .docx
          </button>
        </div>
      )}

      {/* CSV export */}
      <div className="flex justify-end">
        <a
          href={api.csvUrl()}
          className="text-xs text-muted-foreground underline hover:text-foreground"
        >
          Export all as CSV
        </a>
      </div>
    </div>
  )
}
