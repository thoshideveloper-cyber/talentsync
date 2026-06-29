import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { TemplateRecord } from '../api'

interface Props {
  /** Open the freshly-created draft in the Workspace so HR can fill / modify it. */
  onUseTemplate?: (newRecordId: string) => void
}

export function TemplatesView({ onUseTemplate }: Props) {
  const [templates, setTemplates] = useState<TemplateRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cloningId, setCloningId] = useState<string | null>(null)
  const [cloneSuccess, setCloneSuccess] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      setTemplates(await api.listTemplates())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load templates')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const handleClone = async (versionId: string, role: string) => {
    setCloningId(versionId); setCloneSuccess(null)
    try {
      const created = await api.cloneTemplate(versionId)
      setCloneSuccess(`"${role}" copied as a new editable draft — opening it for you…`)
      onUseTemplate?.(created.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create draft from template')
    } finally {
      setCloningId(null)
    }
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        Your organisation's compliance-passing JDs, saved as reusable templates. Pick one for a
        role to spin up a fresh editable draft — then fill in the specifics yourself or ask the AI
        to adapt it in the Workspace.
      </p>

      {loading && (
        <div className="flex items-center justify-center py-20 text-muted-foreground text-sm">
          <span className="inline-block w-4 h-4 border-2 border-muted border-t-primary rounded-full animate-spin mr-2" />
          Loading templates…
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
          <button onClick={() => { setError(null); void load() }} className="ml-2 underline">Retry</button>
        </div>
      )}

      {cloneSuccess && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700 flex items-center gap-2">
          <svg className="h-3.5 w-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          {cloneSuccess}
        </div>
      )}

      {!loading && templates.length === 0 && !error && (
        <div className="rounded-xl border border-dashed border-border px-6 py-14 text-center">
          <p className="text-sm text-muted-foreground">
            No compliance-passing templates yet. Upload a JD and have it pass the compliance gate first.
          </p>
        </div>
      )}

      {!loading && templates.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="text-left font-semibold text-muted-foreground text-xs px-4 py-3">Role</th>
                <th className="text-left font-semibold text-muted-foreground text-xs px-4 py-3 hidden sm:table-cell">
                  Level
                </th>
                <th className="text-left font-semibold text-muted-foreground text-xs px-4 py-3 hidden md:table-cell">
                  Skills
                </th>
                <th className="text-left font-semibold text-muted-foreground text-xs px-4 py-3 hidden lg:table-cell">
                  Source
                </th>
                <th className="text-left font-semibold text-muted-foreground text-xs px-4 py-3 hidden lg:table-cell">
                  Created
                </th>
                <th className="text-right font-semibold text-muted-foreground text-xs px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {templates.map(t => (
                <tr key={t.version_id} className="hover:bg-muted/20 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium text-foreground">{t.role}</div>
                    {t.created_by_email && (
                      <div className="text-xs text-muted-foreground">{t.created_by_email}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs hidden sm:table-cell">
                    {t.ai_seniority}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {(t.required_skills ?? []).slice(0, 4).map(s => (
                        <span key={s}
                          className="inline-flex rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                          {s}
                        </span>
                      ))}
                      {(t.required_skills?.length ?? 0) > 4 && (
                        <span className="text-xs text-muted-foreground">
                          +{(t.required_skills?.length ?? 0) - 4}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs hidden lg:table-cell capitalize">
                    {t.source}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs hidden lg:table-cell">
                    {t.created_at ? new Date(t.created_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => void handleClone(t.version_id, t.role)}
                      disabled={cloningId === t.version_id}
                      className="inline-flex items-center gap-1.5 rounded-md bg-primary/10 px-3 py-1.5 text-xs
                                 font-semibold text-primary hover:bg-primary hover:text-primary-foreground
                                 disabled:opacity-50 transition-colors"
                    >
                      {cloningId === t.version_id ? (
                        <span className="h-3 w-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                      )}
                      Use as template
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && (
        <div className="text-right">
          <button onClick={() => void load()} className="text-xs text-primary hover:underline">
            Refresh
          </button>
        </div>
      )}
    </div>
  )
}
