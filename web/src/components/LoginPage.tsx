import { useState, type FormEvent } from 'react'
import { api } from '../api'
import { authStore } from '../lib/auth'

interface Props {
  onLogin: () => void
}

export function LoginPage({ onLogin }: Props) {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState<string | null>(null)
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const { token, user } = await api.login(email.trim(), password)
      authStore.set(token, user)
      onLogin()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">

      {/* ── Left pane — brand identity (hidden on mobile) ───────────────── */}
      <div
        className="hidden md:flex md:w-[55%] flex-col justify-between p-12 relative overflow-hidden"
        style={{ background: 'hsl(252, 36%, 19%)' }}
      >
        {/* Subtle large-scale background mark */}
        <div
          className="pointer-events-none absolute -bottom-20 -right-20 h-96 w-96 rounded-full opacity-[0.06]"
          style={{ background: 'hsl(252, 50%, 80%)' }}
          aria-hidden
        />
        <div
          className="pointer-events-none absolute top-32 -left-16 h-64 w-64 rounded-full opacity-[0.05]"
          style={{ background: 'hsl(252, 50%, 80%)' }}
          aria-hidden
        />

        {/* Brand mark */}
        <div className="relative z-10 flex items-center gap-2.5">
          <div
            className="rounded-md p-1.5"
            style={{ background: 'hsl(252, 36%, 29%)' }}
          >
            <svg
              className="h-5 w-5"
              style={{ color: 'hsl(252, 50%, 80%)' }}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <span
            className="text-base font-bold tracking-tight"
            style={{ color: 'hsl(252, 12%, 95%)' }}
          >
            TalentSync
          </span>
        </div>

        {/* Hero copy */}
        <div className="relative z-10 flex-1 flex flex-col justify-center py-12">
          <p
            className="text-[10px] font-semibold tracking-[0.15em] uppercase mb-4"
            style={{ color: 'hsl(252, 12%, 62%)' }}
          >
            JD Intelligence Platform
          </p>
          <h1
            className="text-4xl lg:text-5xl font-bold leading-tight tracking-[-0.02em] mb-5"
            style={{
              color: 'hsl(252, 12%, 95%)',
              textWrap: 'balance',
            } as React.CSSProperties}
          >
            Every JD. Precise. Compliant. Ready.
          </h1>
          <p
            className="text-base leading-relaxed max-w-sm"
            style={{ color: 'hsl(252, 12%, 72%)' }}
          >
            AI-powered compliance checks, seniority verification, and audit-grade
            exports — built for India's Labour Code 2025.
          </p>
        </div>

        {/* Feature list */}
        <div className="relative z-10 space-y-2.5">
          {[
            'Compliance check in seconds',
            'Bias flags detected automatically',
            'Audit-grade evidence trail included',
          ].map((item) => (
            <div key={item} className="flex items-center gap-3">
              <div
                className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full"
                style={{ background: 'hsl(252, 36%, 29%)' }}
              >
                <svg
                  className="h-3 w-3"
                  style={{ color: 'hsl(252, 50%, 80%)' }}
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden
                >
                  <path fillRule="evenodd" clipRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
                </svg>
              </div>
              <span
                className="text-sm"
                style={{ color: 'hsl(252, 12%, 72%)' }}
              >
                {item}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right pane — login form ─────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 bg-background">

        {/* Mobile-only brand mark */}
        <div className="md:hidden mb-8 text-center">
          <div className="inline-flex items-center gap-2.5 mb-2">
            <div className="rounded-md bg-primary/10 p-1.5">
              <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="text-base font-bold tracking-tight text-foreground">TalentSync</span>
          </div>
          <p className="text-xs text-muted-foreground">JD Intelligence Platform</p>
        </div>

        <div className="w-full max-w-[22rem]">
          <div className="mb-8">
            <h2 className="text-xl font-bold text-foreground">Sign in to your workspace</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Enter your credentials to continue.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label className="block text-xs font-semibold text-foreground mb-1.5" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoFocus
                autoComplete="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full rounded-lg border border-input bg-card px-3 py-2.5 text-sm text-foreground
                           placeholder:text-muted-foreground
                           focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary
                           transition-colors duration-150"
                placeholder="you@company.com"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-foreground mb-1.5" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full rounded-lg border border-input bg-card px-3 py-2.5 text-sm text-foreground
                           placeholder:text-muted-foreground
                           focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary
                           transition-colors duration-150"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-lg border px-3 py-2.5 text-xs"
                style={{
                  background:   'hsl(17, 65%, 97%)',
                  borderColor:  'hsl(17, 60%, 82%)',
                  color:        'hsl(17, 65%, 38%)',
                }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold
                         text-primary-foreground hover:bg-primary/90
                         disabled:opacity-60 disabled:cursor-not-allowed
                         transition-colors duration-150"
            >
              {loading ? (
                <span className="inline-flex items-center justify-center gap-2">
                  <span className="inline-block h-3.5 w-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" />
                  Signing in
                </span>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-xs text-muted-foreground">
            No account? Contact your workspace admin.
          </p>
        </div>
      </div>

    </div>
  )
}
