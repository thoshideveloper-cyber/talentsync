import { useState } from 'react'
import { api } from '../api'
import type { JobRecord } from '../api'
import { BeforeAfter } from './BeforeAfter'

interface Props {
  onProcessed?: (record: JobRecord) => void
}

export function PasteBox({ onProcessed }: Props) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<JobRecord | null>(null)
  const [copied, setCopied] = useState(false)

  const process = async () => {
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    try {
      const record = await api.extract(text.trim())
      setResult(record)
      onProcessed?.(record)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Extraction failed')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async () => {
    if (!result) return
    try {
      const blob = await api.extractDocx(result.raw_jd)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'corrected_jd.docx'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('Download failed: ' + (e instanceof Error ? e.message : e))
    }
  }

  const handleCopy = async () => {
    if (!result) return
    const text = [
      `${result.role} — ${result.ai_seniority}`,
      result.is_verified ? `Verified: "${result.raw_text_justification}"` : '(unverified)',
      `Skills: ${result.required_skills.join(', ')}`,
      `Summary (indicative): ${result.one_line_summary}`,
      `Score: ${result.quality_score}/100`,
    ].join('\n')
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-4">
      {/* Paste area */}
      <div className="relative">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={`Paste a raw job description here...\n\nExamples:\n• "need someone for the data team, knows python, rockstar mentality"\n• A sparse intake form\n• An old JD copy-paste with manager notes`}
          className="w-full rounded-xl border border-border bg-background p-4 font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring h-48 placeholder:text-muted-foreground"
          disabled={loading}
        />
        {text && (
          <button
            onClick={() => { setText(''); setResult(null); setError(null) }}
            className="absolute top-2 right-2 text-muted-foreground hover:text-foreground"
            title="Clear"
            aria-label="Clear"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={process}
          disabled={loading || !text.trim()}
          className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="inline-block w-4 h-4 border-2 border-primary-foreground/40 border-t-primary-foreground rounded-full animate-spin" />
              Processing...
            </span>
          ) : (
            'Process JD'
          )}
        </button>
        {result && (
          <span className="text-xs text-muted-foreground">
            Result added to dashboard
          </span>
        )}
        {copied && (
          <span className="text-xs text-green-600 font-medium">Copied!</span>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Error: {error}
        </div>
      )}

      {result && (
        <BeforeAfter
          rawText={text.trim()}
          record={result}
          onDownload={handleDownload}
          onCopy={handleCopy}
        />
      )}
    </div>
  )
}
