import type { ComplianceResult } from '../api'

interface Props {
  compliance: ComplianceResult | null
  loading: boolean
}

/**
 * Hero-level verdict banner.
 * Shown at the very top of the Review step so HR sees post-readiness instantly.
 */
export function VerdictBanner({ compliance, loading }: Props) {
  if (loading) {
    return (
      <div className="animate-pulse rounded-2xl border border-border bg-muted/30 p-5">
        <div className="flex items-center gap-4">
          <div className="h-11 w-11 flex-shrink-0 rounded-full bg-muted" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-52 rounded bg-muted" />
            <div className="h-3 w-72 rounded bg-muted" />
          </div>
        </div>
      </div>
    )
  }

  if (!compliance) return null

  const isPass = compliance.verdict === 'pass'
  const total = compliance.high_risk_count + compliance.advisory_count
  const highRisk = compliance.high_risk_count > 0

  const containerCls = isPass
    ? 'border-emerald-200 bg-emerald-50'
    : highRisk
      ? 'border-red-200 bg-red-50'
      : 'border-amber-200 bg-amber-50'

  const iconBg = isPass ? 'bg-emerald-500' : highRisk ? 'bg-red-500' : 'bg-amber-400'

  const headingCls = isPass
    ? 'text-emerald-800'
    : highRisk ? 'text-red-800' : 'text-amber-800'

  const bodyCls = isPass
    ? 'text-emerald-700'
    : highRisk ? 'text-red-700' : 'text-amber-700'

  const subtext = isPass
    ? 'No compliance issues detected. You can download and post this JD immediately.'
    : [
        compliance.high_risk_count > 0
          ? `${compliance.high_risk_count} high-risk filter${compliance.high_risk_count !== 1 ? 's' : ''}`
          : null,
        compliance.advisory_count > 0
          ? `${compliance.advisory_count} advisory note${compliance.advisory_count !== 1 ? 's' : ''}`
          : null,
      ]
        .filter(Boolean)
        .join(' · ') + ' — we recommend fixing these before publishing.'

  return (
    <div className={`rounded-2xl border p-5 ${containerCls}`}>
      <div className="flex items-start gap-4">
        <div className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full ${iconBg}`}>
          {isPass ? (
            <svg className="h-5 w-5 text-white" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
              <path fillRule="evenodd" clipRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
            </svg>
          ) : (
            <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <p className={`text-base font-bold leading-snug ${headingCls}`}>
            {isPass
              ? 'Ready to post — this JD is compliant'
              : `${total} issue${total !== 1 ? 's' : ''} found — this JD needs attention before posting`}
          </p>
          <p className={`mt-1 text-sm ${bodyCls}`}>{subtext}</p>
        </div>
      </div>
    </div>
  )
}
