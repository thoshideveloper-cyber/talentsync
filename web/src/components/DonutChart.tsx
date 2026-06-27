interface Segment {
  label: string
  value: number
  color: string
}

interface Props {
  segments: Segment[]
  centerLabel?: string
  size?: number
}

export function DonutChart({ segments, centerLabel, size = 110 }: Props) {
  const total = segments.reduce((s, g) => s + g.value, 0)
  const r = 38
  const circ = 2 * Math.PI * r
  const GAP = 2.5

  if (total === 0) {
    return (
      <svg width={size} height={size} viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#e2e8f0" strokeWidth="14" />
        <text x="50" y="50" textAnchor="middle" dominantBaseline="middle" fontSize="8" fill="#94a3b8" fontFamily="inherit">
          No data
        </text>
      </svg>
    )
  }

  let accumulated = 0
  return (
    <svg width={size} height={size} viewBox="0 0 100 100">
      <circle cx="50" cy="50" r={r} fill="none" stroke="#f1f5f9" strokeWidth="14" />
      {segments.map((seg, i) => {
        const pct = seg.value / total
        const dashLen = Math.max(0, pct * circ - GAP)
        const startAngle = -90 + (accumulated / total) * 360
        accumulated += seg.value
        if (pct === 0) return null
        return (
          <circle
            key={i}
            cx="50"
            cy="50"
            r={r}
            fill="none"
            stroke={seg.color}
            strokeWidth="14"
            strokeDasharray={`${dashLen} ${circ}`}
            strokeLinecap="butt"
            transform={`rotate(${startAngle} 50 50)`}
          />
        )
      })}
      <text
        x="50"
        y="46"
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize="17"
        fontWeight="700"
        fill="#0f172a"
        fontFamily="inherit"
      >
        {total}
      </text>
      {centerLabel && (
        <text
          x="50"
          y="60"
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="6.5"
          fill="#94a3b8"
          fontFamily="inherit"
          letterSpacing="0.8"
        >
          {centerLabel.toUpperCase()}
        </text>
      )}
    </svg>
  )
}
