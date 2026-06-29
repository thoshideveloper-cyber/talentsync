import { useState } from 'react'
import type { JobRecord } from '../api'
import { PasteBox } from './PasteBox'
import { BatchUpload } from './BatchUpload'
import { IntakeForm } from './IntakeForm'

type InputMode = 'paste' | 'upload' | 'guided'

interface MethodDef {
  id: InputMode
  label: string
  description: string
  badge?: string
  icon: React.ReactNode
}

const METHODS: MethodDef[] = [
  {
    id: 'paste',
    label: 'Paste a JD',
    description: 'Copy and paste from email, Word, or anywhere — we clean and check it instantly.',
    badge: 'Most common',
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
      </svg>
    ),
  },
  {
    id: 'upload',
    label: 'Upload files',
    description: 'Drop in multiple JD files at once. Supports .txt, .docx, and .pdf.',
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
      </svg>
    ),
  },
  {
    id: 'guided',
    label: 'Build from scratch',
    description: 'Fill in a few fields and let AI draft a compliant, structured JD for you.',
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
  },
]

interface Props {
  existingHashes: Set<string>
  onProcessed: (record: JobRecord) => void
}

/**
 * Descriptive card-based method selector.
 * Replaces the old pill toggle — each card explains what the method is for,
 * so HR users know which to pick without trial and error.
 */
export function JdInput({ existingHashes, onProcessed }: Props) {
  const [mode, setMode] = useState<InputMode>('paste')

  return (
    <div className="space-y-6">
      {/* Method cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {METHODS.map(m => {
          const selected = mode === m.id
          return (
            <button
              key={m.id}
              type="button"
              onClick={() => setMode(m.id)}
              className={[
                'relative flex flex-col items-start gap-2.5 rounded-xl border p-4 text-left',
                'transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                selected
                  ? 'border-primary bg-primary/5 shadow-sm'
                  : 'border-border bg-card hover:border-primary/40 hover:bg-muted/30',
              ].join(' ')}
            >
              {/* Selected checkmark */}
              {selected && (
                <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-primary">
                  <svg className="h-3 w-3 text-primary-foreground" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                    <path fillRule="evenodd" clipRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
                  </svg>
                </span>
              )}

              {/* Badge */}
              {m.badge && (
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
                  {m.badge}
                </span>
              )}

              <span className={`${selected ? 'text-primary' : 'text-muted-foreground'}`}>
                {m.icon}
              </span>

              <div>
                <p className={`text-sm font-semibold ${selected ? 'text-primary' : 'text-foreground'}`}>
                  {m.label}
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                  {m.description}
                </p>
              </div>
            </button>
          )
        })}
      </div>

      {/* Active input panel */}
      <div className="rounded-xl border border-border bg-card p-5">
        {mode === 'paste' && <PasteBox onProcessed={onProcessed} />}
        {mode === 'upload' && (
          <BatchUpload
            existingHashes={existingHashes}
            onProcessed={onProcessed}
            onNavigateToBoard={() => { /* navigation handled by Workspace stepper */ }}
          />
        )}
        {mode === 'guided' && <IntakeForm onDraftCreated={onProcessed} />}
      </div>
    </div>
  )
}
