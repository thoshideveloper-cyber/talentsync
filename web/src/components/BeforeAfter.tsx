import type { JobRecord } from '../api'

interface Props {
  rawText: string
  record: JobRecord
  onDownload: () => void
  onCopy: () => void
}

const LEVEL_COLORS: Record<string, string> = {
  'Senior': 'bg-violet-100 text-violet-800 border-violet-200',
  'Executive': 'bg-purple-100 text-purple-800 border-purple-200',
  'Mid-Level': 'bg-blue-100 text-blue-800 border-blue-200',
  'Entry-Level': 'bg-emerald-100 text-emerald-800 border-emerald-200',
  'Internship': 'bg-teal-100 text-teal-800 border-teal-200',
  'Uncertain': 'bg-amber-100 text-amber-800 border-amber-200',
}

function LevelBadge({ level }: { level: string }) {
  const cls = LEVEL_COLORS[level] ?? 'bg-gray-100 text-gray-800 border-gray-200'
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${cls}`}>
      {level}
    </span>
  )
}

export function BeforeAfter({ rawText, record, onDownload, onCopy }: Props) {
  const hasCorrections =
    record.audit_mismatch || record.bias_flags.length > 0 || !record.pay_range_present

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {/* BEFORE */}
      <div className="rounded-xl border border-border bg-muted/40 p-4">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Before — Raw Draft
        </p>
        <pre className="whitespace-pre-wrap break-words font-mono text-sm text-foreground leading-relaxed">
          {rawText}
        </pre>
      </div>

      {/* AFTER */}
      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          After — Normalized
        </p>

        {/* Level + verified */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium">{record.role}</span>
          <span className="text-muted-foreground">—</span>
          <LevelBadge level={record.ai_seniority} />
          {record.is_verified ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 border border-green-200">
              ✓ Verified
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 border border-amber-200">
              ⚠ Unverified
            </span>
          )}
        </div>

        {/* Skills */}
        {record.required_skills.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">Skills (traced)</p>
            <div className="flex flex-wrap gap-1.5">
              {record.required_skills.map((s) => (
                <span key={s} className="rounded border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Verified quote block */}
        {record.is_verified && record.raw_text_justification && (
          <div className="rounded-lg border border-green-200 bg-green-50 p-3">
            <p className="text-xs font-semibold text-green-700 mb-1">Seniority Evidence (Verified)</p>
            <blockquote className="text-sm italic text-green-800">
              "{record.raw_text_justification}"
            </blockquote>
          </div>
        )}

        {/* Indicative summary — visually distinct (R11) */}
        <div className="rounded-lg border border-dashed border-amber-300 bg-amber-50 p-3">
          <p className="text-xs font-semibold text-amber-700 mb-1">
            ✦ Generated Summary — indicative, not verified
          </p>
          <p className="text-sm italic text-amber-900">{record.one_line_summary}</p>
        </div>

        {/* Corrections — the visual hero */}
        {hasCorrections && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 space-y-1.5">
            <p className="text-xs font-semibold text-red-700 mb-1">⚑ Corrections</p>
            {record.audit_mismatch && (
              <p className="text-sm text-red-800">
                <strong>Level mismatch:</strong> stated title suggests "{record.native_label}" but text signals "{record.ai_seniority}" — review before posting.
              </p>
            )}
            {record.bias_flags.length > 0 && (
              <p className="text-sm text-red-800">
                <strong>Language flagged for review:</strong> {record.bias_flags.join(', ')}
              </p>
            )}
            {!record.pay_range_present && (
              <p className="text-sm text-red-800">
                <strong>No pay range:</strong> candidates in India skip postings without compensation info — consider adding.
              </p>
            )}
          </div>
        )}

        {/* Score */}
        <div className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2">
          <div>
            <p className="text-xs font-medium text-muted-foreground">Quality Score</p>
            <p className="text-lg font-bold">{record.quality_score}<span className="text-sm font-normal text-muted-foreground">/100</span></p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">{record.score_breakdown.join(' · ')}</p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-1">
          <button
            onClick={onDownload}
            className="flex-1 rounded-lg border border-primary bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            ⬇ Download .docx
          </button>
          <button
            onClick={onCopy}
            className="rounded-lg border px-3 py-2 text-sm font-medium hover:bg-muted/50 transition-colors"
            title="Copy normalized text"
          >
            📋 Copy
          </button>
        </div>
      </div>
    </div>
  )
}
