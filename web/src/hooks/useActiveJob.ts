import { useCallback, useEffect, useSyncExternalStore } from 'react'
import { api } from '../api'
import type { JobRecord, ComplianceResult } from '../api'

/**
 * Single source of truth for "the JD currently in focus".
 *
 * Replaces the three duplicated "select a role" dropdowns + independent
 * compliance fetches that used to live in the Compliance / Transform / Refine
 * tabs. Any surface that needs the active JD subscribes to the same store, so
 * focusing a role in one place carries everywhere (DRY + sequential flow).
 */

interface ActiveJobState {
  recordId: string | null
  record: JobRecord | null
  compliance: ComplianceResult | null
  complianceLoading: boolean
}

const initial: ActiveJobState = {
  recordId: null,
  record: null,
  compliance: null,
  complianceLoading: false,
}

let state: ActiveJobState = initial
const listeners = new Set<() => void>()

function emit() {
  for (const l of listeners) l()
}

function set(patch: Partial<ActiveJobState>) {
  state = { ...state, ...patch }
  emit()
}

function subscribe(cb: () => void) {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

function getSnapshot() {
  return state
}

/**
 * Focus a JD by record id. Loads its record + compliance once and caches it on
 * the store. Pass `records` so we can resolve the record without an extra fetch.
 */
export async function focusJob(recordId: string | null, records: JobRecord[]) {
  if (!recordId) {
    set({ recordId: null, record: null, compliance: null, complianceLoading: false })
    return
  }
  // Already focused on this record — keep cached compliance.
  if (state.recordId === recordId && state.compliance) return

  const record = records.find(r => r.id === recordId) ?? null
  set({ recordId, record, compliance: null, complianceLoading: true })
  try {
    const compliance = await api.complianceChecks(recordId)
    // Guard against a race where focus changed while we were fetching.
    if (state.recordId === recordId) set({ compliance, complianceLoading: false })
  } catch {
    if (state.recordId === recordId) set({ complianceLoading: false })
  }
}

/** Drop any cached compliance for the active job (e.g. after a transform/refine). */
export function refreshActiveCompliance() {
  if (state.recordId) {
    const id = state.recordId
    set({ compliance: null, complianceLoading: true })
    api.complianceChecks(id)
      .then(c => { if (state.recordId === id) set({ compliance: c, complianceLoading: false }) })
      .catch(() => { if (state.recordId === id) set({ complianceLoading: false }) })
  }
}

export function clearActiveJob() {
  state = initial
  emit()
}

/**
 * Subscribe to the active-job store. `records` lets focus() resolve the record
 * object; keep it stable from the parent.
 */
export function useActiveJob(records: JobRecord[]) {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot)

  const focus = useCallback(
    (recordId: string | null) => void focusJob(recordId, records),
    [records],
  )

  // Keep the cached record in sync if the records list updates (e.g. a transform
  // produced a fresh version) without losing focus.
  useEffect(() => {
    if (snapshot.recordId) {
      const fresh = records.find(r => r.id === snapshot.recordId)
      if (fresh && fresh !== snapshot.record) set({ record: fresh })
    }
  }, [records, snapshot.recordId, snapshot.record])

  return {
    ...snapshot,
    focus,
    refreshCompliance: refreshActiveCompliance,
    clear: clearActiveJob,
  }
}
