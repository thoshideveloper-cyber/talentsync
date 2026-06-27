import type { JobRecord } from '../api'

interface Props {
  records: JobRecord[]
}

export function LevelingView({ records }: Props) {
  const mismatches = records.filter((r) => r.audit_mismatch)
  const mismatchRate = records.length > 0 ? Math.round((mismatches.length / records.length) * 100) : 0
  const verifiedMismatches = mismatches.filter(r => r.is_verified).length
  const cleanRoles = records.length - mismatches.length

  if (records.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-16 text-center text-sm text-muted-foreground">
        No records yet. Process a job description to see leveling analysis.
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Analytics strip */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-border bg-card p-4 text-center">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Mismatch Rate</p>
          <p className={`text-2xl font-bold tabular-nums mt-1 leading-none ${mismatchRate > 20 ? 'text-red-600' : 'text-foreground'}`}>
            {mismatchRate}%
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">{mismatches.length} of {records.length} roles</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 text-center">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Evidence Found</p>
          <p className="text-2xl font-bold tabular-nums mt-1 leading-none text-emerald-600">{verifiedMismatches}</p>
          <p className="text-xs text-muted-foreground mt-0.5">verified quotes</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 text-center">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Clean Roles</p>
          <p className="text-2xl font-bold tabular-nums mt-1 leading-none text-foreground">{cleanRoles}</p>
          <p className="text-xs text-muted-foreground mt-0.5">no level gap detected</p>
        </div>
      </div>

      {mismatches.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
          No leveling flags in the current dataset.
        </div>
      ) : (
        <div className="space-y-3">
          {mismatches.map((rec) => (
            <div key={rec.id} className="rounded-xl border border-border bg-card overflow-hidden">
              <div className="flex">
                <div className="w-1 bg-red-400 shrink-0" />
                <div className="flex-1 p-4 space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="font-semibold text-foreground text-sm">{rec.role}</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">{rec.id} · {rec.input_format}</p>
                    </div>
                    <span className="shrink-0 rounded-full bg-red-50 border border-red-200 px-2.5 py-0.5 text-xs font-semibold text-red-600">
                      Level Gap
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg border border-border bg-muted/30 p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">Stated Title</p>
                      <p className="font-semibold text-red-600 text-sm">{rec.native_label ?? '(not stated)'}</p>
                    </div>
                    <div className="rounded-lg border border-border bg-muted/30 p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">Text Signals</p>
                      <p className="font-semibold text-emerald-600 text-sm">{rec.ai_seniority}</p>
                    </div>
                  </div>

                  {rec.is_verified && rec.raw_text_justification && (
                    <div className="rounded-lg border border-emerald-200 bg-emerald-50/40 p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-700 mb-1.5">Verified Evidence</p>
                      <blockquote className="text-sm italic text-emerald-900">"{rec.raw_text_justification}"</blockquote>
                    </div>
                  )}

                  {!rec.is_verified && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50/40 p-2.5">
                      <p className="text-xs text-amber-700">Source quote could not be verified — seniority defaulted to Uncertain.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
