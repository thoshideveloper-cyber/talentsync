interface StepDef {
  n: number
  label: string
  sublabel: string
}

interface Props {
  steps: readonly StepDef[]
  current: number
  canNavigateTo: (n: number) => boolean
  onNavigate: (n: number) => void
}

function stepStatus(n: number, current: number): 'done' | 'active' | 'future' {
  if (n < current) return 'done'
  if (n === current) return 'active'
  return 'future'
}

/**
 * Compact horizontal stepper. Each step is a small pill; done steps get a
 * filled accent, active step gets a primary ring, future steps are muted.
 * Connector lines are thin and low-contrast so the steps read at a glance.
 */
export function WorkspaceStepHeader({ steps, current, canNavigateTo, onNavigate }: Props) {
  return (
    <nav aria-label="Progress" className="w-full">
      <ol className="flex w-full items-center">
        {steps.map((step, index) => {
          const status = stepStatus(step.n, current)
          const navigable = canNavigateTo(step.n)
          const isLast = index === steps.length - 1

          return (
            <li key={step.n} className={`flex ${isLast ? '' : 'flex-1'} items-center`}>
              {/* Step pill */}
              <button
                type="button"
                disabled={!navigable}
                onClick={() => navigable && onNavigate(step.n)}
                aria-current={status === 'active' ? 'step' : undefined}
                className={[
                  'group flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold',
                  'transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary whitespace-nowrap',
                  status === 'done'
                    ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 cursor-pointer'
                    : status === 'active'
                      ? 'bg-primary text-primary-foreground shadow-sm cursor-default'
                      : navigable
                        ? 'bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer'
                        : 'bg-muted/30 text-muted-foreground/40 cursor-not-allowed',
                ].join(' ')}
              >
                {/* Number / checkmark */}
                <span className={[
                  'flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold shrink-0',
                  status === 'done'
                    ? 'bg-emerald-500 text-white'
                    : status === 'active'
                      ? 'bg-white/20 text-inherit'
                      : 'bg-border/60 text-muted-foreground/60',
                ].join(' ')}>
                  {status === 'done' ? (
                    <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                      <path fillRule="evenodd" clipRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
                    </svg>
                  ) : step.n}
                </span>
                <span className="leading-none">{step.label}</span>
              </button>

              {/* Connector */}
              {!isLast && (
                <div className={`flex-1 h-px mx-2 rounded-full transition-colors duration-300 ${
                  status === 'done' ? 'bg-emerald-300' : 'bg-border'
                }`} />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
