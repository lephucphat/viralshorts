/**
 * Circular 0-99 clip score. The colour band is fixed (>= 80 strong, 60-79 ok,
 * below weak) so the same number always looks the same everywhere.
 *
 * Props: value (number | null), size (px, default 44), label (optional caption)
 * Renders nothing when the score is not a finite number: never show a made-up 0.
 */
function scoreTone(value) {
  if (!Number.isFinite(value)) return 'mid';
  if (value >= 80) return 'hi';
  if (value >= 60) return 'mid';
  return 'lo';
}

const TONE_VAR = {
  hi: 'var(--color-score-hi)',
  mid: 'var(--color-score-mid)',
  lo: 'var(--color-score-lo)',
};

export default function ScoreRing({ value, size = 44, label }) {
  if (!Number.isFinite(value)) return null;
  const score = Math.max(0, Math.min(99, Math.round(value)));
  const stroke = Math.max(3, Math.round(size / 11));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = TONE_VAR[scoreTone(score)];
  return (
    <div className="inline-flex flex-col items-center gap-1" role="img" aria-label={label ? `${label}: ${score}` : String(score)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-rule-2)" strokeWidth={stroke} />
          <circle
            cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
            strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - score / 99)}
            style={{ transition: 'stroke-dashoffset 600ms var(--ease-out)' }}
          />
        </svg>
        <span
          className="absolute inset-0 flex items-center justify-center font-semibold text-ink tabular-nums"
          style={{ fontSize: Math.round(size * 0.34) }}
        >
          {score}
        </span>
      </div>
      {label && <span className="text-micro text-muted">{label}</span>}
    </div>
  );
}
