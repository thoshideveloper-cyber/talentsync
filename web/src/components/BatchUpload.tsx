import { useState, useRef, useCallback } from 'react'
import { api } from '../api'
import type { JobRecord } from '../api'

type FileStatus = 'pending' | 'processing' | 'done' | 'duplicate' | 'failed'

interface FileEntry {
  id: string
  file: File
  status: FileStatus
  record?: JobRecord
  error?: string
}

interface Props {
  existingHashes: Set<string>
  onProcessed: (record: JobRecord) => void
  onNavigateToBoard: () => void
}

const ACCEPTED = '.txt,.docx,.pdf,.md'

const LEVEL_COLORS: Record<string, string> = {
  'Executive': 'text-purple-700',
  'Senior': 'text-violet-700',
  'Mid-Level': 'text-blue-700',
  'Entry-Level': 'text-emerald-700',
  'Internship': 'text-teal-700',
  'Uncertain': 'text-amber-700',
}

function RowIcon({ status }: { status: FileStatus }) {
  if (status === 'processing') {
    return (
      <span className="inline-block w-3.5 h-3.5 border-2 border-border border-t-primary rounded-full animate-spin" />
    )
  }
  const map: Record<FileStatus, string> = {
    done: 'text-emerald-500',
    duplicate: 'text-blue-400',
    failed: 'text-red-500',
    pending: 'text-muted-foreground',
    processing: '',
  }
  const glyph: Record<FileStatus, string> = {
    done: '✓',
    duplicate: '≡',
    failed: '✕',
    pending: '○',
    processing: '',
  }
  return <span className={`text-sm ${map[status]}`}>{glyph[status]}</span>
}

function rowBg(status: FileStatus) {
  return status === 'done' ? 'bg-emerald-50/40'
    : status === 'failed' ? 'bg-red-50/40'
    : status === 'processing' ? 'bg-blue-50/30'
    : status === 'duplicate' ? 'bg-muted/30'
    : ''
}

function statusText(entry: FileEntry) {
  if (entry.status === 'done' && entry.record) {
    const lvl = entry.record.ai_seniority
    return (
      <span className={LEVEL_COLORS[lvl] ?? 'text-muted-foreground'}>
        {lvl} · {entry.record.quality_score}/100
      </span>
    )
  }
  if (entry.status === 'duplicate') return <span className="text-blue-500">Already in system</span>
  if (entry.status === 'processing') return <span className="text-blue-600">Processing…</span>
  if (entry.status === 'failed') return <span className="text-red-600 truncate">{entry.error ?? 'Failed'}</span>
  return <span className="text-muted-foreground">Pending</span>
}

function fmt(bytes: number) {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function BatchUpload({ existingHashes, onProcessed, onNavigateToBoard }: Props) {
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [processing, setProcessing] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [batchDone, setBatchDone] = useState(false)

  const fileRef = useRef<HTMLInputElement>(null)
  const folderRef = useRef<HTMLInputElement>(null)

  const addFiles = useCallback((incoming: File[]) => {
    const valid = incoming.filter(f => {
      const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
      return ['txt', 'docx', 'pdf', 'md'].includes(ext)
    })
    setEntries(prev => {
      const seen = new Set(prev.map(e => e.file.name + e.file.size))
      const fresh = valid.filter(f => !seen.has(f.name + f.size))
      return [
        ...prev,
        ...fresh.map(file => ({
          id: Math.random().toString(36).slice(2),
          file,
          status: 'pending' as FileStatus,
        })),
      ]
    })
    setBatchDone(false)
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    addFiles(Array.from(e.dataTransfer.files))
  }, [addFiles])

  const onFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(e.target.files ?? []))
    e.target.value = ''
  }

  const processAll = async () => {
    const pending = entries.filter(e => e.status === 'pending')
    if (!pending.length || processing) return
    setProcessing(true)
    setBatchDone(false)

    const seenHashes = new Set<string>(existingHashes)

    for (const entry of pending) {
      setEntries(prev => prev.map(e =>
        e.id === entry.id ? { ...e, status: 'processing' } : e
      ))
      try {
        const record = await api.extractFile(entry.file)
        const isDuplicate = seenHashes.has(record.content_hash)
        seenHashes.add(record.content_hash)
        setEntries(prev => prev.map(e =>
          e.id === entry.id
            ? { ...e, status: isDuplicate ? 'duplicate' : 'done', record }
            : e
        ))
        if (!isDuplicate) onProcessed(record)
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error'
        setEntries(prev => prev.map(e =>
          e.id === entry.id ? { ...e, status: 'failed', error: msg } : e
        ))
      }
    }

    setProcessing(false)
    setBatchDone(true)
  }

  const clearAll = () => {
    if (processing) return
    setEntries([])
    setBatchDone(false)
  }

  const retryFailed = () => {
    setEntries(prev => prev.map(e =>
      e.status === 'failed' ? { ...e, status: 'pending', error: undefined, record: undefined } : e
    ))
    setBatchDone(false)
  }

  const pendingCount = entries.filter(e => e.status === 'pending').length
  const doneCount = entries.filter(e => e.status === 'done').length
  const duplicateCount = entries.filter(e => e.status === 'duplicate').length
  const failedCount = entries.filter(e => e.status === 'failed').length
  const processed = entries.length - pendingCount
  const progressPct = entries.length > 0 ? (processed / entries.length) * 100 : 0

  return (
    <div className="space-y-4">

      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => !processing && fileRef.current?.click()}
        className={`rounded-xl border-2 border-dashed transition-all cursor-pointer select-none ${
          dragOver
            ? 'border-primary bg-primary/5 scale-[1.01]'
            : 'border-border hover:border-primary/50 hover:bg-muted/20'
        } p-10 text-center`}
      >
        <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-muted">
          <svg className="h-5 w-5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
        </div>
        <p className="text-sm font-medium text-foreground">
          {dragOver ? 'Drop to add files' : 'Drop JD files here, or click to browse'}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Supports .txt · .docx · .pdf — select multiple files or an entire folder
        </p>
      </div>

      {/* Hidden inputs */}
      <input
        ref={fileRef}
        type="file"
        multiple
        accept={ACCEPTED}
        className="hidden"
        onChange={onFileInput}
      />
      <input
        ref={folderRef}
        type="file"
        // @ts-expect-error webkitdirectory is not in React's HTML typedefs
        webkitdirectory=""
        multiple
        className="hidden"
        onChange={onFileInput}
      />

      {/* Shortcut buttons (when queue is empty) */}
      {entries.length === 0 && (
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => fileRef.current?.click()}
            className="rounded-xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground hover:bg-muted/40 transition-colors"
          >
            Select Files
          </button>
          <button
            onClick={() => folderRef.current?.click()}
            className="rounded-xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground hover:bg-muted/40 transition-colors"
          >
            Select Folder
          </button>
        </div>
      )}

      {/* Queue */}
      {entries.length > 0 && (
        <div className="space-y-3">

          {/* Queue header */}
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-foreground">
              {entries.length} file{entries.length !== 1 ? 's' : ''} queued
            </p>
            <div className="flex items-center gap-2">
              {!processing && (
                <>
                  <button
                    onClick={() => fileRef.current?.click()}
                    className="rounded-md border border-border px-2.5 py-1 text-xs font-medium hover:bg-muted/50 transition-colors"
                  >
                    Add Files
                  </button>
                  <button
                    onClick={() => folderRef.current?.click()}
                    className="rounded-md border border-border px-2.5 py-1 text-xs font-medium hover:bg-muted/50 transition-colors"
                  >
                    Add Folder
                  </button>
                  <button
                    onClick={clearAll}
                    className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground hover:bg-muted/50 transition-colors"
                  >
                    Clear
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Progress bar */}
          {(processing || batchDone) && (
            <div>
              <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <p className="mt-1 text-[10px] text-muted-foreground">
                {processed} of {entries.length} processed
              </p>
            </div>
          )}

          {/* File rows */}
          <div className="rounded-xl border border-border overflow-hidden divide-y divide-border">
            {entries.map(entry => (
              <div
                key={entry.id}
                className={`flex items-center gap-3 px-4 py-3 transition-colors ${rowBg(entry.status)}`}
              >
                <div className="w-4 shrink-0 flex items-center justify-center">
                  <RowIcon status={entry.status} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{entry.file.name}</p>
                  <p className="text-xs mt-0.5">{statusText(entry)}</p>
                </div>
                <span className="text-xs text-muted-foreground shrink-0 tabular-nums">
                  {fmt(entry.file.size)}
                </span>
                {entry.status === 'done' && entry.record && (
                  <div className="shrink-0 w-16 text-right">
                    <div
                      className="h-1 rounded-full bg-muted overflow-hidden"
                      title={`Score: ${entry.record.quality_score}/100`}
                    >
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${entry.record.quality_score}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Process button */}
          {pendingCount > 0 && (
            <button
              onClick={processAll}
              disabled={processing}
              className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60 transition-colors flex items-center justify-center gap-2"
            >
              {processing ? (
                <>
                  <span className="inline-block w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                  Processing…
                </>
              ) : (
                `Process ${pendingCount} File${pendingCount !== 1 ? 's' : ''}`
              )}
            </button>
          )}

          {/* Completion summary */}
          {batchDone && !processing && (
            <div className="rounded-xl border border-border bg-card p-5">
              <p className="text-sm font-semibold text-foreground mb-3">Batch complete</p>
              <div className="flex flex-wrap gap-5">
                {doneCount > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                    <span className="text-sm">
                      <span className="font-bold text-foreground">{doneCount}</span>
                      <span className="text-muted-foreground"> processed</span>
                    </span>
                  </div>
                )}
                {duplicateCount > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-blue-400 shrink-0" />
                    <span className="text-sm">
                      <span className="font-bold text-foreground">{duplicateCount}</span>
                      <span className="text-muted-foreground"> already in system</span>
                    </span>
                  </div>
                )}
                {failedCount > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-red-400 shrink-0" />
                    <span className="text-sm">
                      <span className="font-bold text-foreground">{failedCount}</span>
                      <span className="text-muted-foreground"> failed</span>
                    </span>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-4 mt-4 pt-3 border-t border-border">
                {doneCount > 0 && (
                  <button
                    onClick={onNavigateToBoard}
                    className="text-sm font-semibold text-primary hover:underline"
                  >
                    View in Roles Board →
                  </button>
                )}
                {failedCount > 0 && (
                  <button
                    onClick={retryFailed}
                    className="text-sm font-medium text-muted-foreground hover:text-foreground"
                  >
                    Retry failed
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
