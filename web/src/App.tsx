import { useEffect, useState } from 'react'
import { api } from './api'
import type { JobRecord, KpiData, SkillFreq } from './api'
import { authStore } from './lib/auth'
import { LoginPage } from './components/LoginPage'
import { KpiStrip } from './components/KpiStrip'
import { Workspace } from './components/Workspace'
import { RolesView } from './components/RolesView'
import { InsightsView } from './components/InsightsView'
import { focusJob, clearActiveJob } from './hooks/useActiveJob'

type Tab = 'workspace' | 'roles' | 'insights'

const TABS: { id: Tab; label: string }[] = [
  { id: 'workspace', label: 'Workspace' },
  { id: 'roles', label: 'Roles' },
  { id: 'insights', label: 'Insights' },
]

export default function App() {
  const [authed, setAuthed] = useState(authStore.isAuthenticated())
  const [tab, setTab] = useState<Tab>('workspace')
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
      if (e instanceof Error && e.message === 'Session expired') return
      setError(e instanceof Error ? e.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (authed) void load()
    else setLoading(false)
  }, [authed])

  const handleLogin = () => {
    setAuthed(true)
    setLoading(true)
    void load()
  }

  const handleLogout = () => {
    authStore.clear()
    clearActiveJob()
    setAuthed(false)
    setRecords([])
    setKpis(null)
    setSkills([])
  }

  const handleTabChange = (t: Tab) => {
    setTab(t)
    if (t !== 'workspace') void load()
  }

  // A JD was processed or transformed: merge it in and refresh KPIs/skills.
  const handleChanged = async (record?: JobRecord) => {
    if (record) {
      setRecords(prev =>
        prev.some(r => r.id === record.id) ? prev.map(r => r.id === record.id ? record : r) : [...prev, record]
      )
    } else {
      await load()
      return
    }
    try {
      const [kData, sData] = await Promise.all([api.kpis(), api.skills()])
      setKpis(kData)
      setSkills(sData)
    } catch { /* non-fatal */ }
  }

  // Open a role from Roles → focus it and jump to the Workspace review step.
  const handleOpenRole = (recordId: string) => {
    void focusJob(recordId, records)
    setTab('workspace')
  }

  if (!authed) return <LoginPage onLogin={handleLogin} />

  const user = authStore.getUser()

  return (
    <div className="min-h-screen bg-background">
      <header
        className="sticky top-0 z-10 border-b"
        style={{ background: 'hsl(252, 36%, 19%)', borderColor: 'hsl(252, 30%, 28%)' }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center justify-between">

            {/* Wordmark */}
            <div className="flex items-center gap-2.5">
              <div className="rounded-md p-1.5" style={{ background: 'hsl(252, 36%, 29%)' }}>
                <svg
                  className="h-4 w-4"
                  style={{ color: 'hsl(252, 50%, 80%)' }}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <span className="text-sm font-bold tracking-tight" style={{ color: 'hsl(252, 12%, 95%)' }}>
                TalentSync
              </span>
            </div>

            {/* Navigation */}
            <nav className="flex items-center gap-0.5">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => handleTabChange(t.id)}
                  className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors duration-150 ${
                    tab === t.id
                      ? 'bg-white'
                      : 'text-white/60 hover:text-white/90 hover:bg-white/10'
                  }`}
                  style={tab === t.id ? { color: 'hsl(252, 36%, 19%)' } : {}}
                >
                  {t.label}
                </button>
              ))}
            </nav>

            {/* User */}
            <div className="flex items-center gap-2">
              {user && (
                <span className="hidden sm:block text-xs" style={{ color: 'hsl(252, 12%, 62%)' }}>
                  {user.email}
                  <span className="mx-1 opacity-50">·</span>
                  <span className="capitalize">{user.role}</span>
                </span>
              )}
              <button
                onClick={handleLogout}
                className="rounded-md px-3 py-1.5 text-xs font-semibold
                           text-white/60 hover:text-white/90 hover:bg-white/10 transition-colors duration-150"
              >
                Sign out
              </button>
            </div>

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
            {tab === 'workspace' && (
              <Workspace records={records} onChanged={handleChanged} />
            )}

            {tab === 'roles' && (
              <RolesView records={records} onOpenRole={handleOpenRole} onBulkFixed={() => void load()} />
            )}

            {tab === 'insights' && (
              <InsightsView records={records} skills={skills} onUseTemplate={(id) => { void focusJob(id, records); setTab('workspace') }} />
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
