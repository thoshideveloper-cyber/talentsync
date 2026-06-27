import { useEffect, useState } from 'react'
import { api } from './api'
import type { JobRecord, KpiData, SkillFreq } from './api'
import { PasteBox } from './components/PasteBox'
import { KpiStrip } from './components/KpiStrip'
import { Board } from './components/Board'
import { LevelingView } from './components/LevelingView'
import { SkillsView } from './components/SkillsView'
import { BeforeAfter } from './components/BeforeAfter'
import { BatchUpload } from './components/BatchUpload'

type Tab = 'paste' | 'board' | 'leveling' | 'skills' | 'batch'

const TABS: { id: Tab; label: string }[] = [
  { id: 'paste', label: 'Quality Gate' },
  { id: 'board', label: 'Roles' },
  { id: 'leveling', label: 'Leveling' },
  { id: 'skills', label: 'Analytics' },
  { id: 'batch', label: 'Batch Upload' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('paste')
  const [records, setRecords] = useState<JobRecord[]>([])
  const [kpis, setKpis] = useState<KpiData | null>(null)
  const [skills, setSkills] = useState<SkillFreq[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      const [recs, kData, sData] = await Promise.all([
        api.records(),
        api.kpis(),
        api.skills(),
      ])
      setRecords(recs)
      setKpis(kData)
      setSkills(sData)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const handleTabChange = (t: Tab) => {
    setTab(t)
    if (t !== 'paste') void load()
  }

  const handleProcessed = async (record: JobRecord) => {
    setRecords(prev =>
      prev.some(r => r.content_hash === record.content_hash)
        ? prev
        : [...prev, record]
    )
    try {
      const [kData, sData] = await Promise.all([api.kpis(), api.skills()])
      setKpis(kData)
      setSkills(sData)
    } catch {}
  }

  const handleLastRunDownload = (rec: JobRecord) => {
    window.open(api.docxUrl(rec.id), '_blank')
  }

  const handleLastRunCopy = async (rec: JobRecord) => {
    const lines = [
      `${rec.role} — ${rec.ai_seniority}`,
      rec.is_verified ? `Verified: "${rec.raw_text_justification}"` : '(unverified)',
      `Skills: ${rec.required_skills.join(', ')}`,
      `Summary (indicative): ${rec.one_line_summary}`,
      `Score: ${rec.quality_score}/100`,
    ]
    await navigator.clipboard.writeText(lines.join('\n'))
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/90 backdrop-blur-sm sticky top-0 z-10">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="rounded-lg bg-primary/10 p-1.5">
                <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <span className="text-sm font-bold tracking-tight text-foreground">TalentSync</span>
            </div>
            <nav className="flex items-center gap-0.5">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => handleTabChange(t.id)}
                  className={`rounded-md px-3 py-1.5 text-xs font-semibold tracking-wide transition-colors ${
                    tab === t.id
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/60'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {kpis && !loading && (
          <div className="mb-7">
            <KpiStrip kpis={kpis} />
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-20 text-muted-foreground text-sm">
            <span className="inline-block w-4 h-4 border-2 border-muted border-t-primary rounded-full animate-spin mr-2" />
            Loading
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            Could not connect to API: {error}. Make sure the backend is running on port 8000.
          </div>
        )}

        {!loading && (
          <>
            {tab === 'paste' && (
              <section>
                <div className="mb-5">
                  <h2 className="text-lg font-bold text-foreground">Quality Gate</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Paste a raw job draft to normalize and verify it. Every seniority call is backed by an exact quote from source text.
                  </p>
                </div>
                <PasteBox onProcessed={handleProcessed} />

                {records.length > 0 && (() => {
                  const last = records[records.length - 1]
                  return (
                    <div className="mt-12">
                      <div className="flex items-center gap-3 mb-5">
                        <div className="h-px flex-1 bg-border" />
                        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                          Last Run · {last.role}
                        </span>
                        <div className="h-px flex-1 bg-border" />
                      </div>
                      <BeforeAfter
                        rawText={last.raw_jd}
                        record={last}
                        onDownload={() => handleLastRunDownload(last)}
                        onCopy={() => handleLastRunCopy(last)}
                      />
                    </div>
                  )
                })()}
              </section>
            )}

            {tab === 'board' && (
              <section>
                <div className="mb-5">
                  <h2 className="text-lg font-bold text-foreground">Role Intelligence</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {records.length} processed role{records.length !== 1 ? 's' : ''} — sort by level, score, or status. Click any row for the grounding quote.
                  </p>
                </div>
                <Board records={records} />
              </section>
            )}

            {tab === 'leveling' && (
              <section>
                <div className="mb-5">
                  <h2 className="text-lg font-bold text-foreground">Leveling Analysis</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Roles where the stated title and text signals disagree by two or more tiers.
                  </p>
                </div>
                <LevelingView records={records} />
              </section>
            )}

            {tab === 'skills' && (
              <section>
                <div className="mb-5">
                  <h2 className="text-lg font-bold text-foreground">Analytics</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Workforce composition, skill demand, and quality metrics across all processed roles.
                  </p>
                </div>
                <SkillsView skills={skills} total={records.length} records={records} />
              </section>
            )}

            {tab === 'batch' && (
              <section>
                <div className="mb-5">
                  <h2 className="text-lg font-bold text-foreground">Batch Upload</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Upload multiple JD files at once. Each file is parsed and run through the full extraction pipeline — results appear in Roles, Leveling, and Analytics immediately.
                  </p>
                </div>
                <BatchUpload
                  existingHashes={new Set(records.map(r => r.content_hash))}
                  onProcessed={handleProcessed}
                  onNavigateToBoard={() => handleTabChange('board')}
                />
              </section>
            )}
          </>
        )}
      </main>

      <footer className="border-t border-border mt-16 py-4 text-center text-xs text-muted-foreground">
        TalentSync · Seniority verified against source quotes · Summaries indicative only
      </footer>
    </div>
  )
}
