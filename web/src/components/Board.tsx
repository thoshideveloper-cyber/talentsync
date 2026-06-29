import { useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import type { JobRecord } from '../api'
import { api } from '../api'

interface Props {
  records: JobRecord[]
  onOpenRole?: (recordId: string) => void
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

export function Board({ records, onOpenRole }: Props) {
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

  const handleDownload = (rec: JobRecord, e: React.MouseEvent) => {
    e.stopPropagation()
    void api.downloadDocx(rec.id).catch(err => console.error('Download failed', err))
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
    <Dialog.Root open={!!selected} onOpenChange={open => { if (!open) setSelected(null) }}>
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
                    onClick={() => setSelected(rec)}
                  >
                    <td className="px-3 py-3">
                      <div className="font-medium text-foreground">{rec.role}</div>
                      <div className="text-[10px] text-muted-foreground font-mono">{rec.id.slice(0, 8)}…</div>
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
                          <span className="rounded bg-red-50 border border-red-200 px-1.5 py-0.5 text-xs text-red-700">level mismatch</span>
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
                        {onOpenRole && (
                          <button
                            onClick={() => onOpenRole(rec.id)}
                            className="rounded border border-primary/40 bg-primary/5 px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10 transition-colors"
                            title="Open in Workspace"
                          >
                            Open →
                          </button>
                        )}
                        <button
                          onClick={(e) => toggleExpand(rec.id, e)}
                          className={`rounded border px-2 py-1 text-xs transition-colors ${
                            expanded.has(rec.id)
                              ? 'bg-muted border-border text-foreground'
                              : 'hover:bg-muted/50 border-border'
                          }`}
                          title="Toggle raw source text"
                        >
                          Raw {expanded.has(rec.id) ? '▲' : '▼'}
                        </button>
                        <button
                          onClick={(e) => handleDownload(rec, e)}
                          className="rounded border border-border px-2 py-1 text-xs hover:bg-muted/50 transition-colors"
                          title="Download corrected .docx"
                        >
                          .docx
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expanded.has(rec.id) && (
                    <tr key={`${rec.id}-raw`} className="bg-muted/20">
                      <td colSpan={7} className="px-4 pb-3 pt-2">
                        <p className="text-xs font-semibold text-muted-foreground mb-1.5">Raw source text</p>
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

        {/* CSV export */}
        <div className="flex justify-end">
          <button
            onClick={() => void api.downloadCsv().catch(e => console.error('Export failed', e))}
            className="text-xs text-muted-foreground underline hover:text-foreground"
          >
            Export all as CSV
          </button>
        </div>
      </div>

      {/* ── Slide-over detail drawer ───────────────────────────────────────── */}
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className="fixed inset-y-0 right-0 z-50 w-full max-w-md border-l border-border bg-card shadow-2xl
                     focus:outline-none overflow-y-auto
                     data-[state=open]:animate-in data-[state=closed]:animate-out
                     data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right
                     duration-300"
        >
          {selected && (
            <div className="flex flex-col h-full">
              {/* Header */}
              <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4 sticky top-0 bg-card z-10">
                <div className="min-w-0">
                  <Dialog.Title className="text-base font-bold text-foreground truncate">{selected.role}</Dialog.Title>
                  <p className="text-xs text-muted-foreground mt-0.5 font-mono">{selected.id.slice(0, 8)}… · {selected.input_format}</p>
                </div>
                <Dialog.Close asChild>
                  <button
                    className="rounded-md p-1.5 hover:bg-muted transition-colors text-muted-foreground hover:text-foreground shrink-0"
                    aria-label="Close"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </Dialog.Close>
              </div>

              {/* Body */}
              <div className="flex-1 space-y-4 px-5 py-5">
                {/* Level badge */}
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${LEVEL_COLORS[selected.ai_seniority] ?? 'bg-gray-100 text-gray-800'}`}>
                    {selected.ai_seniority}
                  </span>
                  <span className={`text-xs font-medium ${
                    selected.status === 'ok' ? 'text-green-600' :
                    selected.status === 'unverified' ? 'text-amber-600' : 'text-red-600'
                  }`}>
                    {selected.status}
                  </span>
                  <span className="text-xs font-bold tabular-nums ml-auto">
                    {selected.quality_score}<span className="text-muted-foreground font-normal">/100</span>
                  </span>
                </div>

                {/* Grounding quote */}
                <div className="rounded-lg border bg-muted/30 p-3">
                  <p className="text-xs font-semibold text-muted-foreground mb-1">
                    Seniority evidence {selected.is_verified ? '(verified)' : '(unverified)'}
                  </p>
                  <blockquote className="text-sm italic text-foreground">
                    {selected.raw_text_justification || '—'}
                  </blockquote>
                </div>

                {/* Indicative summary */}
                <div className="rounded-lg border border-dashed border-amber-300 bg-amber-50 p-3">
                  <p className="text-xs font-semibold text-amber-700 mb-1">AI-generated summary — indicative only</p>
                  <p className="text-sm italic text-amber-900">{selected.one_line_summary}</p>
                </div>

                {/* Flags */}
                {selected.bias_flags.length > 0 && (
                  <div className="rounded-lg border border-orange-200 bg-orange-50 p-3">
                    <p className="text-xs font-semibold text-orange-700 mb-2">Flagged language — review before posting</p>
                    <div className="flex flex-wrap gap-1.5">
                      {selected.bias_flags.map(flag => (
                        <span key={flag} className="rounded border border-orange-300 bg-white px-2 py-0.5 text-xs font-medium text-orange-800">
                          {flag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selected.audit_mismatch && (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-3">
                    <p className="text-xs font-semibold text-red-700">
                      Level mismatch — stated "{selected.native_label}" but text signals "{selected.ai_seniority}"
                    </p>
                  </div>
                )}

                {/* Skills */}
                {selected.required_skills.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground mb-2">Required skills</p>
                    <div className="flex flex-wrap gap-1.5">
                      {selected.required_skills.map(s => (
                        <span key={s} className="rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700 border border-blue-200">{s}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Score breakdown */}
                <div>
                  <p className="text-xs font-semibold text-muted-foreground mb-1">Score breakdown</p>
                  <p className="text-sm">{selected.quality_score}/100 · {selected.score_breakdown.join(' · ') || '—'}</p>
                </div>

                {/* Raw JD */}
                <div>
                  <p className="text-xs font-semibold text-muted-foreground mb-1.5">Source text</p>
                  <pre className="rounded-lg bg-muted/40 p-3 text-xs whitespace-pre-wrap break-words font-mono max-h-52 overflow-y-auto leading-relaxed">
                    {selected.raw_jd}
                  </pre>
                </div>
              </div>

              {/* Footer actions */}
              <div className="border-t border-border px-5 py-4 flex gap-2 sticky bottom-0 bg-card">
                {onOpenRole && (
                  <button
                    onClick={() => { onOpenRole(selected.id); setSelected(null) }}
                    className="flex-1 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
                  >
                    Open in Workspace →
                  </button>
                )}
                <button
                  onClick={() => void api.downloadDocx(selected.id).catch(e => console.error('Download failed', e))}
                  className="rounded-lg border border-border px-4 py-2.5 text-sm font-semibold text-foreground hover:bg-muted/60 transition-colors"
                >
                  Download .docx
                </button>
              </div>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
