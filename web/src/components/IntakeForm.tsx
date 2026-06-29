import { useState, useEffect, useRef, type KeyboardEvent } from 'react'
import { api } from '../api'
import type { IntakeResult, PayHintResult } from '../api'
import { CompliancePanel } from './CompliancePanel'

const LEVELS = ['Internship', 'Entry-Level', 'Mid-Level', 'Senior', 'Executive'] as const
type Level = typeof LEVELS[number]

interface Props {
  onDraftCreated?: (result: IntakeResult) => void
}

export function IntakeForm({ onDraftCreated }: Props) {
  const [role, setRole] = useState('')
  const [level, setLevel] = useState<Level>('Mid-Level')
  const [location, setLocation] = useState('')
  const [payBand, setPayBand] = useState('')
  const [notes, setNotes] = useState('')
  const [mustHaves, setMustHaves] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<IntakeResult | null>(null)
  // CompliancePanel auto-loads its own data; we never toggle this manually.
  const complianceLoading = false
  // Pay hints
  const [payHint, setPayHint] = useState<PayHintResult | null>(null)
  const hintTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Fetch pay hint whenever role or level changes (debounced 800ms)
  useEffect(() => {
    if (hintTimerRef.current) clearTimeout(hintTimerRef.current)
    if (!role.trim()) { setPayHint(null); return }
    hintTimerRef.current = setTimeout(() => {
      api.payHints(role.trim(), level)
        .then(h => setPayHint(h))
        .catch(() => { /* silently ignore hint errors */ })
    }, 800)
    return () => { if (hintTimerRef.current) clearTimeout(hintTimerRef.current) }
  }, [role, level])

  const addTag = (raw: string) => {
    const tag = raw.trim()
    if (tag && !mustHaves.includes(tag)) {
      setMustHaves(prev => [...prev, tag])
    }
    setTagInput('')
  }

  const onTagKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addTag(tagInput)
    } else if (e.key === 'Backspace' && tagInput === '' && mustHaves.length > 0) {
      setMustHaves(prev => prev.slice(0, -1))
    }
  }

  const removeTag = (tag: string) => {
    setMustHaves(prev => prev.filter(t => t !== tag))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!role.trim() || !location.trim() || !payBand.trim() || mustHaves.length === 0) {
      setError('Role, location, pay band, and at least one requirement are needed.')
      return
    }
    setError(null)
    setLoading(true)
    setResult(null)
    try {
      const res = await api.intakeDraft({ role, level, must_haves: mustHaves, location, pay_band: payBand, notes })
      setResult(res)
      onDraftCreated?.(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Draft generation failed')
    } finally {
      setLoading(false)
    }
  }

  const verdictColor = (v: 'pass' | 'warn') =>
    v === 'pass' ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-amber-700 bg-amber-50 border-amber-200'

  return (
    <div className="space-y-8">
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Role + Level */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-foreground mb-1">
              Role / Title <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              value={role}
              onChange={e => setRole(e.target.value)}
              placeholder="e.g. Senior Software Engineer"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              Seniority Level <span className="text-destructive">*</span>
            </label>
            <select
              value={level}
              onChange={e => setLevel(e.target.value as Level)}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
        </div>

        {/* Pay hint inline tip */}
        {payHint && payHint.matched_count > 0 && (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700 flex items-start gap-2">
            <svg className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{payHint.hint}</span>
          </div>
        )}

        {/* Location + Pay Band */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              Location <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              value={location}
              onChange={e => setLocation(e.target.value)}
              placeholder="e.g. Bengaluru (Hybrid)"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              Pay Band <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              value={payBand}
              onChange={e => setPayBand(e.target.value)}
              placeholder="e.g. ₹20–28 LPA"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
        </div>

        {/* Must-haves tag input */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">
            Must-Have Skills / Requirements <span className="text-destructive">*</span>
          </label>
          <div
            className="min-h-[42px] flex flex-wrap gap-1.5 rounded-lg border border-input bg-background
                       px-3 py-2 focus-within:ring-2 focus-within:ring-primary/50 cursor-text"
            onClick={() => document.getElementById('tag-input')?.focus()}
          >
            {mustHaves.map(tag => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-0.5
                           text-xs font-medium text-primary"
              >
                {tag}
                <button
                  type="button"
                  onClick={e => { e.stopPropagation(); removeTag(tag) }}
                  className="hover:text-destructive leading-none"
                >
                  ×
                </button>
              </span>
            ))}
            <input
              id="tag-input"
              type="text"
              value={tagInput}
              onChange={e => setTagInput(e.target.value)}
              onKeyDown={onTagKeyDown}
              onBlur={() => tagInput && addTag(tagInput)}
              placeholder={mustHaves.length === 0 ? 'Type a skill and press Enter…' : ''}
              className="flex-1 min-w-[120px] bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Press Enter or comma to add each skill/requirement.
          </p>
        </div>

        {/* Additional Notes */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">
            Additional Notes
            <span className="ml-1 text-xs font-normal text-muted-foreground">(optional)</span>
          </label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={3}
            placeholder="Any specific context, culture notes, team size, or requirements to include…"
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
          />
        </div>

        {error && (
          <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm
                     font-semibold text-primary-foreground hover:bg-primary/90 transition-colors
                     disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {loading && (
            <span className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground
                             rounded-full animate-spin" />
          )}
          {loading ? 'Generating draft…' : 'Generate Compliant Draft'}
        </button>
      </form>

      {/* Result */}
      {result && (
        <div className="space-y-6 border-t border-border pt-6">
          {/* Compliance summary badge */}
          <div className={`inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold ${
            verdictColor(result.compliance_summary.verdict)
          }`}>
            {result.compliance_summary.verdict === 'pass' ? (
              <>
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Draft passes compliance check
              </>
            ) : (
              <>
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
                {result.compliance_summary.high_risk_count} high-risk issue{result.compliance_summary.high_risk_count !== 1 ? 's' : ''} found
                {result.compliance_summary.advisory_count > 0 &&
                  ` · ${result.compliance_summary.advisory_count} advisory`}
              </>
            )}
          </div>

          {/* Draft JD text */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-bold text-foreground">Generated Draft</h3>
              <div className="flex gap-2">
                <button
                  onClick={() => navigator.clipboard.writeText(result.raw_jd)}
                  className="rounded-md px-3 py-1.5 text-xs font-semibold border border-border
                             text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                >
                  Copy
                </button>
                <button
                  type="button"
                  onClick={() => void api.downloadDocx(result.id).catch(e => console.error('Download failed', e))}
                  className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs
                             font-semibold border border-border text-muted-foreground
                             hover:text-foreground hover:bg-muted/60 transition-colors"
                >
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  Download DOCX
                </button>
              </div>
            </div>
            <pre className="rounded-xl border border-border bg-muted/30 p-4 text-xs leading-relaxed
                           whitespace-pre-wrap font-sans overflow-auto max-h-[500px]">
              {result.raw_jd}
            </pre>
          </div>

          {/* Intake meta tags */}
          <div className="flex flex-wrap gap-2 text-xs">
            {[
              `Level: ${result.intake_meta.level}`,
              `Location: ${result.intake_meta.location}`,
              `Pay: ${result.intake_meta.pay_band}`,
              ...result.intake_meta.must_haves.map(s => `${s}`),
            ].map((tag, i) => (
              <span key={i} className="rounded-md bg-muted px-2.5 py-1 text-muted-foreground font-medium">
                {tag}
              </span>
            ))}
          </div>

          {/* Full compliance panel */}
          <div>
            <h3 className="text-sm font-bold text-foreground mb-3">Compliance Details</h3>
            <CompliancePanel
              recordId={result.id}
              versionId={result.version_id ?? ''}
              result={null}
              loading={complianceLoading}
              autoLoad
            />
          </div>
        </div>
      )}
    </div>
  )
}
