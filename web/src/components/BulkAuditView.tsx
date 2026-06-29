import { useRef, useState } from 'react'
import { api } from '../api'
import type { BulkAuditResult, BulkAuditJdResult, BulkAuditFinding } from '../api'
import { ruleLabel as ruleShort } from '../lib/ruleLabels'

// ── Helpers ───────────────────────────────────────────────────────────────────

function riskBadge(tier: string) {
  if (tier === 'high_risk')
    return (
      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold
                        bg-red-100 text-red-700">
        High-Risk
      </span>
    )
  return (
    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold
                      bg-amber-100 text-amber-700">
      Advisory
    </span>
  )
}

// ── Summary cards ─────────────────────────────────────────────────────────────

function SummaryCard({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div className={`rounded-xl border ${color} px-4 py-3`}>
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-0.5">{value}</p>
    </div>
  )
}

// ── Per-JD row ────────────────────────────────────────────────────────────────

function JdRow({
  result,
  expanded,
  onToggle,
}: {
  result: BulkAuditJdResult
  expanded: boolean
  onToggle: () => void
}) {
  const isHigh = result.high_risk_count > 0
  const isAdvisory = result.advisory_count > 0

  return (
    <div className={`rounded-lg border transition-colors ${
      isHigh ? 'border-red-200' : isAdvisory ? 'border-amber-200' : 'border-green-200'
    }`}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/20 transition-colors"
      >
        {/* Status dot */}
        <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${
          isHigh ? 'bg-red-500' : isAdvisory ? 'bg-amber-400' : 'bg-green-500'
        }`} />

        {/* Label */}
        <span className="flex-1 text-sm font-medium text-foreground truncate" title={result.label}>
          {result.label}
        </span>

        {/* Counts */}
        <div className="flex items-center gap-2 shrink-0">
          {isHigh && (
            <span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-red-100 text-red-700">
              {result.high_risk_count} high-risk
            </span>
          )}
          {isAdvisory && (
            <span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-amber-100 text-amber-700">
              {result.advisory_count} advisory
            </span>
          )}
          {!isHigh && !isAdvisory && (
            <span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-green-100 text-green-700">
              Clean
            </span>
          )}
        </div>

        {/* Chevron */}
        <svg
          className={`h-4 w-4 text-muted-foreground shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && result.findings.length > 0 && (
        <div className="border-t border-inherit px-4 py-3 space-y-3">
          {result.findings.map((f, i) => (
            <FindingDetail key={i} finding={f} />
          ))}
        </div>
      )}

      {expanded && result.findings.length === 0 && (
        <div className="border-t border-green-200 px-4 py-3 text-sm text-green-700">
          No compliance issues detected for this JD.
        </div>
      )}
    </div>
  )
}

function FindingDetail({ finding }: { finding: BulkAuditFinding }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        {riskBadge(finding.risk_tier)}
        <span className="text-sm font-medium">{ruleShort(finding.rule_id)}</span>
        {finding.evidence_span && (
          <button
            onClick={() => setOpen(o => !o)}
            className="text-xs text-muted-foreground hover:text-foreground ml-auto"
          >
            {open ? 'Hide' : 'Show'} evidence
          </button>
        )}
      </div>
      {open && finding.evidence_span && (
        <blockquote className={`text-xs italic rounded px-3 py-2 ${
          finding.risk_tier === 'high_risk' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'
        }`}>
          {finding.evidence_span}
        </blockquote>
      )}
    </div>
  )
}

// ── Rules-triggered breakdown ──────────────────────────────────────────────────

function RulesBreakdown({ rules }: { rules: Record<string, number> }) {
  const sorted = Object.entries(rules).sort(([, a], [, b]) => b - a)
  if (!sorted.length) return null
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        Rules Triggered
      </p>
      <div className="space-y-2">
        {sorted.map(([rule, count]) => (
          <div key={rule} className="flex items-center justify-between">
            <span className="text-sm text-foreground">{ruleShort(rule)}</span>
            <span className="text-sm font-bold text-foreground">{count} JD{count !== 1 ? 's' : ''}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function BulkAuditView() {
  const [result, setResult] = useState<BulkAuditResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [dragOver, setDragOver] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const fileRef = useRef<HTMLInputElement>(null)

  const toggle = (i: number) =>
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })

  const expandAll = () =>
    setExpanded(new Set((result?.results ?? []).map((_, i) => i)))

  const collapseAll = () => setExpanded(new Set())

  const handleFiles = (incoming: FileList | File[]) => {
    const arr = Array.from(incoming).filter(f =>
      /\.(txt|docx|pdf)$/i.test(f.name)
    )
    if (!arr.length) {
      setError('Upload .txt, .docx, or .pdf files.')
      return
    }
    setFiles(arr)
    setResult(null)
    setError(null)
  }

  const runAudit = async () => {
    if (!files.length) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.bulkAuditFiles(files)
      setResult(data)
      setExpanded(new Set())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Audit failed')
    } finally {
      setLoading(false)
    }
  }

  const downloadCsv = async () => {
    if (!result) return
    // Export from the existing result client-side (no JD text round-trip needed).
    const rows = ['index,label,verdict,high_risk_count,advisory_count,rule_id,risk_tier,evidence_span']
    for (const r of result.results) {
      if (r.findings.length) {
        for (const f of r.findings) {
          rows.push([
            r.index,
            `"${r.label.replace(/"/g, '""')}"`,
            r.verdict,
            r.high_risk_count,
            r.advisory_count,
            f.rule_id,
            f.risk_tier,
            `"${(f.evidence_span ?? '').replace(/"/g, '""')}"`,
          ].join(','))
        }
      } else {
        rows.push([r.index, `"${r.label}"`, r.verdict, 0, 0, '', '', ''].join(','))
      }
    }
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'bulk_compliance_audit.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      {/* Upload area */}
      <div
        className={`rounded-xl border-2 border-dashed transition-colors p-8 text-center cursor-pointer ${
          dragOver ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
        }`}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => {
          e.preventDefault()
          setDragOver(false)
          handleFiles(e.dataTransfer.files)
        }}
        onClick={() => fileRef.current?.click()}
      >
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".txt,.docx,.pdf"
          className="hidden"
          onChange={e => e.target.files && handleFiles(e.target.files)}
        />
        <svg className="mx-auto h-10 w-10 text-muted-foreground mb-3" fill="none"
          viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <p className="text-sm font-semibold text-foreground">
          Drop JD files here or click to select
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          .txt · .docx · .pdf — up to 500 files per batch
        </p>
      </div>

      {/* File list + Audit button */}
      {files.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-foreground">
              {files.length} file{files.length !== 1 ? 's' : ''} selected
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => { setFiles([]); setResult(null) }}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                Clear
              </button>
              <button
                onClick={runAudit}
                disabled={loading}
                className="rounded-md px-4 py-1.5 text-sm font-semibold bg-primary text-primary-foreground
                           hover:bg-primary/90 transition-colors disabled:opacity-60"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="inline-block w-3.5 h-3.5 border-2 border-primary-foreground/30
                                      border-t-primary-foreground rounded-full animate-spin" />
                    Auditing…
                  </span>
                ) : `Audit ${files.length} JD${files.length !== 1 ? 's' : ''}`}
              </button>
            </div>
          </div>
          <div className="space-y-1">
            {files.slice(0, 10).map(f => (
              <div key={f.name} className="flex items-center gap-2 text-xs text-muted-foreground">
                <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {f.name}
              </div>
            ))}
            {files.length > 10 && (
              <p className="text-xs text-muted-foreground">+{files.length - 10} more files</p>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Verdict banner */}
          <div className={`rounded-xl border px-5 py-4 ${
            result.high_risk_jds > 0
              ? 'border-red-200 bg-red-50'
              : result.at_risk_jds > 0
                ? 'border-amber-200 bg-amber-50'
                : 'border-green-200 bg-green-50'
          }`}>
            <p className={`text-base font-bold ${
              result.high_risk_jds > 0 ? 'text-red-700'
                : result.at_risk_jds > 0 ? 'text-amber-700'
                : 'text-green-700'
            }`}>
              {result.verdict_summary}
            </p>
          </div>

          {/* Summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <SummaryCard label="Total JDs" value={result.total} color="border-border" />
            <SummaryCard
              label="High-Risk"
              value={result.high_risk_jds}
              color={result.high_risk_jds > 0 ? 'border-red-200 text-red-700' : 'border-border'}
            />
            <SummaryCard
              label="Advisory Only"
              value={result.advisory_only_jds}
              color={result.advisory_only_jds > 0 ? 'border-amber-200 text-amber-700' : 'border-border'}
            />
            <SummaryCard
              label="Clean"
              value={result.clean_jds}
              color={result.clean_jds > 0 ? 'border-green-200 text-green-700' : 'border-border'}
            />
          </div>

          {/* Rules breakdown + Export */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <RulesBreakdown rules={result.rules_triggered} />
            </div>
            <div className="flex flex-col justify-start gap-2 pt-1">
              <button
                onClick={downloadCsv}
                className="rounded-md px-4 py-2 text-sm font-semibold border border-border
                           text-foreground hover:bg-muted/60 transition-colors"
              >
                Export CSV
              </button>
            </div>
          </div>

          {/* Per-JD results */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">
                Per-JD Drill-Down
              </p>
              <div className="flex gap-2 text-xs text-muted-foreground">
                <button onClick={expandAll} className="hover:text-foreground">Expand all</button>
                <span>·</span>
                <button onClick={collapseAll} className="hover:text-foreground">Collapse all</button>
              </div>
            </div>
            {result.results.map((r, i) => (
              <JdRow
                key={i}
                result={r}
                expanded={expanded.has(i)}
                onToggle={() => toggle(i)}
              />
            ))}
          </div>

          {/* Recall caveat */}
          <p className="text-xs text-muted-foreground border-t border-border pt-3">
            Recall caveat: detectors catch explicit written filters only. Implicit or coded
            bias is outside scope. Not a legal opinion — seek qualified legal advice before
            treating any finding as a confirmed violation.
          </p>
        </div>
      )}
    </div>
  )
}
