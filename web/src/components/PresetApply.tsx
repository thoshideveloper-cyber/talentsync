import { useState, useEffect } from 'react'
import { api } from '../api'
import type { Preset, TransformResult } from '../api'
import { CompliancePanel } from './CompliancePanel'

interface Props {
  recordId: string
  currentVersionId: string
  roleName?: string
  onTransformed?: (result: TransformResult) => void
}

export function PresetApply({ recordId, roleName, onTransformed }: Props) {
  const [presets, setPresets] = useState<Preset[]>([])
  const [selectedPresetId, setSelectedPresetId] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [presetsLoading, setPresetsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<TransformResult | null>(null)

  useEffect(() => {
    api.listPresets()
      .then(data => {
        setPresets(data)
        if (data.length > 0) setSelectedPresetId(data[0].id)
      })
      .catch(() => setError('Could not load presets'))
      .finally(() => setPresetsLoading(false))
  }, [])

  const handleApply = async () => {
    if (!selectedPresetId) return
    setError(null)
    setLoading(true)
    setResult(null)
    try {
      const res = await api.applyTransform(recordId, selectedPresetId)
      setResult(res)
      onTransformed?.(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transform failed')
    } finally {
      setLoading(false)
    }
  }

  const verdictBadge = (v: 'pass' | 'warn') =>
    v === 'pass'
      ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
      : 'text-amber-700 bg-amber-50 border-amber-200'

  if (presetsLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
        <span className="w-4 h-4 border-2 border-muted border-t-primary rounded-full animate-spin" />
        Loading presets…
      </div>
    )
  }

  if (presets.length === 0) {
    return (
      <p className="text-sm text-muted-foreground rounded-xl border border-dashed border-border px-4 py-6 text-center">
        No active presets. An admin can create presets via the API.
      </p>
    )
  }

  return (
    <div className="space-y-5">
      <p className="text-xs text-muted-foreground">
        Apply a transformation preset to{roleName ? ` "${roleName}"` : ' this JD'}.
        A new versioned copy is created — the original is preserved.
      </p>

      {/* Preset selector */}
      <div className="flex flex-col sm:flex-row gap-3">
        <select
          value={selectedPresetId}
          onChange={e => setSelectedPresetId(e.target.value)}
          disabled={loading}
          className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm
                     focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-60"
        >
          {presets.map(p => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <button
          onClick={handleApply}
          disabled={loading || !selectedPresetId}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm
                     font-semibold text-primary-foreground hover:bg-primary/90 transition-colors
                     disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap"
        >
          {loading && (
            <span className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground
                             rounded-full animate-spin" />
          )}
          {loading ? 'Rewriting…' : 'Apply Preset'}
        </button>
      </div>

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-5 border-t border-border pt-5">
          {/* Compliance summary */}
          <div className={`inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold ${
            verdictBadge(result.compliance_summary.verdict)
          }`}>
            {result.compliance_summary.verdict === 'pass' ? (
              <>
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Rewritten JD passes compliance check
              </>
            ) : (
              <>
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
                {result.compliance_summary.high_risk_count} high-risk issue{result.compliance_summary.high_risk_count !== 1 ? 's' : ''} remain
              </>
            )}
          </div>

          {/* Preset + version provenance */}
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-md bg-muted px-2.5 py-1 text-muted-foreground font-medium">
              Preset: {result.transform_meta.preset_name}
            </span>
            <span className="rounded-md bg-muted px-2.5 py-1 text-muted-foreground font-medium">
              Source version: {result.transform_meta.parent_version_id.slice(0, 8)}…
            </span>
            <span className="rounded-md bg-muted px-2.5 py-1 text-muted-foreground font-medium">
              New version: {result.version_id?.slice(0, 8)}…
            </span>
          </div>

          {/* Rewritten JD text */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-bold text-foreground">Rewritten JD</h4>
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
                           whitespace-pre-wrap font-sans overflow-auto max-h-[480px]">
              {result.raw_jd}
            </pre>
          </div>

          {/* Full compliance panel for new version */}
          <div>
            <h4 className="text-sm font-bold text-foreground mb-3">New Version Compliance</h4>
            <CompliancePanel
              recordId={result.id}
              versionId={result.version_id ?? ''}
              result={null}
              loading={false}
              autoLoad
            />
          </div>
        </div>
      )}
    </div>
  )
}
