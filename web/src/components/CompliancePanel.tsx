import { useState, useEffect } from 'react'
import type { ComplianceCheck, ComplianceResult } from '../api'
import { api } from '../api'
import { authStore } from '../lib/auth'

interface Props {
  recordId: string
  versionId: string
  result: ComplianceResult | null
  loading?: boolean
  /** When true, auto-fetch compliance data on mount if result is null */
  autoLoad?: boolean
}

const TIER_LABEL: Record<string, string> = {
  high_risk: 'High-Risk Filter',
  advisory: 'Advisory',
}

const RULE_SHORT: Record<string, string> = {
  'filter.age_cap': 'Age Cap',
  'filter.gender_preference': 'Gender Preference',
  'filter.marital_status': 'Marital Status',
  'filter.community_caste': 'Caste / Community / Category',
  'filter.disability_exclusion': 'Disability Exclusion',
  'filter.maternity_status': 'Pregnancy / Maternity Filter',
  'filter.freshers_only': 'Freshers Only',
  'pay.disclosure_absent': 'No Pay Disclosure',
  'quality.leveling_mismatch': 'Leveling Mismatch',
  'quality.unverified_seniority': 'Unverified Seniority',
}

function ruleShort(ruleId: string): string {
  if (ruleId in RULE_SHORT) return RULE_SHORT[ruleId]
  if (ruleId.startsWith('language.inclusive.')) {
    const term = ruleId.replace('language.inclusive.', '').replace(/_/g, ' ')
    return `Language: "${term}"`
  }
  return ruleId
}

function CheckRow({ check, expanded, onToggle }: {
  check: ComplianceCheck
  expanded: boolean
  onToggle: () => void
}) {
  const isHigh = check.risk_tier === 'high_risk'

  return (
    <div
      className={`rounded-lg border transition-colors ${
        isHigh
          ? 'border-red-200 bg-red-50'
          : 'border-amber-200 bg-amber-50'
      }`}
    >
      <button
        onClick={onToggle}
        className="w-full flex items-start gap-3 px-4 py-3 text-left"
      >
        <span className={`mt-0.5 shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${
          isHigh
            ? 'bg-red-100 text-red-700'
            : 'bg-amber-100 text-amber-700'
        }`}>
          {TIER_LABEL[check.risk_tier] ?? check.risk_tier}
        </span>
        <span className="flex-1 text-sm font-medium text-foreground">
          {ruleShort(check.rule_id)}
        </span>
        <svg
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-inherit pt-3">
          {check.evidence_span && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                Evidence
              </p>
              <blockquote className={`text-sm italic rounded-md px-3 py-2 ${
                isHigh ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'
              }`}>
                {check.evidence_span}
              </blockquote>
            </div>
          )}
          {check.citation && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                Citation
              </p>
              <p className="text-xs text-muted-foreground leading-relaxed">{check.citation}</p>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            Rule ID: <code className="font-mono">{check.rule_id}</code>
          </p>
        </div>
      )}
    </div>
  )
}

function OverrideModal({
  recordId,
  versionId,
  onClose,
  onSuccess,
}: {
  recordId: string
  versionId: string
  onClose: () => void
  onSuccess: () => void
}) {
  const [justification, setJustification] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!justification.trim()) {
      setError('Justification is required.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await api.complianceOverride(recordId, versionId, justification.trim())
      onSuccess()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Override failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-lg">
        <div className="px-6 py-4 border-b border-border">
          <h3 className="text-base font-bold text-foreground">Override Compliance Warning</h3>
          <p className="text-xs text-muted-foreground mt-1">
            This action is recorded in the append-only audit trail. Provide a documented
            business justification.
          </p>
        </div>
        <div className="px-6 py-4 space-y-3">
          <label className="block text-sm font-medium text-foreground">
            Business Justification
          </label>
          <textarea
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
            rows={4}
            placeholder="Describe why this posting complies with applicable law and policy despite the flagged language…"
            value={justification}
            onChange={e => setJustification(e.target.value)}
          />
          {error && (
            <p className="text-xs text-red-600">{error}</p>
          )}
        </div>
        <div className="px-6 py-4 border-t border-border flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md px-4 py-2 text-sm font-medium text-muted-foreground
                       hover:text-foreground hover:bg-muted/60 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={submitting}
            className="rounded-md px-4 py-2 text-sm font-semibold bg-primary text-primary-foreground
                       hover:bg-primary/90 transition-colors disabled:opacity-60"
          >
            {submitting ? 'Submitting…' : 'Submit Override'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function CompliancePanel({ recordId, versionId, result: resultProp, loading: loadingProp, autoLoad }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [showOverride, setShowOverride] = useState(false)
  const [overrideSuccess, setOverrideSuccess] = useState(false)
  const [autoResult, setAutoResult] = useState<ComplianceResult | null>(null)
  const [autoLoading, setAutoLoading] = useState(false)

  useEffect(() => {
    if (autoLoad && !resultProp && recordId) {
      setAutoLoading(true)
      api.complianceChecks(recordId)
        .then(r => setAutoResult(r))
        .catch(() => {})
        .finally(() => setAutoLoading(false))
    }
  }, [autoLoad, recordId, resultProp])

  const result = resultProp ?? autoResult
  const loading = loadingProp || autoLoading

  const user = authStore.getUser()
  const canOverride = user?.role === 'approver' || user?.role === 'admin'

  const toggle = (id: string) =>
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
        <span className="inline-block w-4 h-4 border-2 border-muted border-t-primary
                          rounded-full animate-spin" />
        Checking compliance…
      </div>
    )
  }

  if (!result) return null

  const highRisk = result.checks.filter(c => c.risk_tier === 'high_risk')
  const advisory = result.checks.filter(c => c.risk_tier === 'advisory')
  const isWarn = result.verdict === 'warn' && highRisk.length > 0

  return (
    <div className="space-y-4">
      {/* Verdict banner */}
      <div className={`flex items-center justify-between rounded-xl border px-4 py-3 ${
        isWarn
          ? 'border-red-200 bg-red-50'
          : advisory.length > 0
            ? 'border-amber-200 bg-amber-50'
            : 'border-green-200 bg-green-50'
      }`}>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-bold ${
            isWarn ? 'text-red-700' : advisory.length > 0 ? 'text-amber-700' : 'text-green-700'
          }`}>
            {isWarn
              ? `${highRisk.length} High-Risk Filter${highRisk.length !== 1 ? 's' : ''} Detected`
              : advisory.length > 0
                ? `${advisory.length} Advisory Note${advisory.length !== 1 ? 's' : ''}`
                : 'No Compliance Issues'}
          </span>
          {!isWarn && advisory.length === 0 && (
            <span className="text-xs text-green-600 font-medium">Passed all checks</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {canOverride && isWarn && !overrideSuccess && (
            <button
              onClick={() => setShowOverride(true)}
              className="rounded-md px-3 py-1.5 text-xs font-semibold bg-white border
                         border-red-300 text-red-700 hover:bg-red-50 transition-colors"
            >
              Override with Justification
            </button>
          )}
          {overrideSuccess && (
            <span className="text-xs font-medium text-green-700 bg-green-100 px-2 py-1 rounded-full">
              Override recorded
            </span>
          )}
        </div>
      </div>

      {/* High-risk findings */}
      {highRisk.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-red-600">
            High-Risk Filters ({highRisk.length})
          </p>
          {highRisk.map((c, i) => (
            <CheckRow
              key={`${c.rule_id}-${i}`}
              check={c}
              expanded={expanded.has(`${c.rule_id}-${i}`)}
              onToggle={() => toggle(`${c.rule_id}-${i}`)}
            />
          ))}
        </div>
      )}

      {/* Advisory findings */}
      {advisory.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-600">
            Advisory ({advisory.length})
          </p>
          {advisory.map((c, i) => (
            <CheckRow
              key={`${c.rule_id}-advisory-${i}`}
              check={c}
              expanded={expanded.has(`${c.rule_id}-advisory-${i}`)}
              onToggle={() => toggle(`${c.rule_id}-advisory-${i}`)}
            />
          ))}
        </div>
      )}

      {/* Recall caveat */}
      <p className="text-xs text-muted-foreground border-t border-border pt-3">
        Recall caveat: these detectors catch explicit written filters only. Implicit bias
        in otherwise-neutral language is outside scope. Not a legal opinion.
      </p>

      {showOverride && (
        <OverrideModal
          recordId={recordId}
          versionId={versionId}
          onClose={() => setShowOverride(false)}
          onSuccess={() => {
            setShowOverride(false)
            setOverrideSuccess(true)
          }}
        />
      )}
    </div>
  )
}
