import { useState, useRef, useEffect } from 'react'
import { api } from '../api'

interface QAEntry {
  question: string
  answer: string
  not_in_jd: boolean
  ts: number
}

interface Props {
  recordId: string
  roleName?: string
}

export function ChatPanel({ recordId, roleName }: Props) {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<QAEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault()
    const q = question.trim()
    if (!q) return
    setError(null)
    setLoading(true)
    try {
      const res = await api.askAboutJd(recordId, q)
      setHistory(prev => [...prev, {
        question: q,
        answer: res.answer,
        not_in_jd: res.not_in_jd,
        ts: Date.now(),
      }])
      setQuestion('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const SUGGESTED = [
    'What is the required experience level?',
    'What skills are mentioned?',
    'Is a salary range stated?',
    'What are the key responsibilities?',
    'Is remote work mentioned?',
  ]

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">
        Ask any question about{roleName ? ` "${roleName}"` : ' this JD'}.
        Answers are grounded strictly to the JD text — if the information isn't there,
        you'll see "Not stated in this JD."
      </p>

      {/* Suggested questions */}
      {history.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTED.map(q => (
            <button
              key={q}
              type="button"
              onClick={() => setQuestion(q)}
              className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground
                         hover:text-foreground hover:bg-muted/60 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Q&A history */}
      {history.length > 0 && (
        <div className="space-y-3 rounded-xl border border-border bg-muted/20 p-4 max-h-80 overflow-y-auto">
          {history.map(entry => (
            <div key={entry.ts} className="space-y-1.5">
              <p className="text-xs font-semibold text-foreground">Q: {entry.question}</p>
              <div className={`rounded-lg px-3 py-2 text-xs leading-relaxed ${
                entry.not_in_jd
                  ? 'bg-muted text-muted-foreground italic'
                  : 'bg-background border border-border text-foreground'
              }`}>
                {entry.answer}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </p>
      )}

      {/* Input */}
      <form onSubmit={handleAsk} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          placeholder="Ask a question about this JD…"
          disabled={loading}
          className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm
                     focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm
                     font-semibold text-primary-foreground hover:bg-primary/90 transition-colors
                     disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground
                             rounded-full animate-spin" />
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          )}
          Ask
        </button>
      </form>
    </div>
  )
}
