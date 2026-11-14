import { useEffect, useMemo, useState } from 'react';
import { Check, Loader2, Download, Mic, Sparkles, Clapperboard, Clock } from 'lucide-react';
import { useLang } from '../contexts/LangContext';

// The pipeline reports itself only through log lines, so the stage is read from
// them. Order matters: the furthest stage seen wins, so a re-run line from an
// earlier stage can never move the display backwards.
const STAGES = [
  { id: 'download', icon: Download, test: /download|tải/i },
  { id: 'transcribe', icon: Mic, test: /transcrib/i },
  { id: 'analyze', icon: Sparkles, test: /analy[sz]|shortlist|scoring window|found \d+ clips|local llm|gemini/i },
  { id: 'render', icon: Clapperboard, test: /creating clip|clip \d+ ready|clip_ready/i },
];

function readProgress(logs) {
  const lines = Array.isArray(logs) ? logs : [];
  let stage = -1;
  lines.forEach((line) => {
    STAGES.forEach((s, i) => { if (i > stage && s.test.test(String(line))) stage = i; });
  });
  let percent = null;
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const m = /transcribing….*?(\d+)%/i.exec(String(lines[i]));
    if (m) { percent = Math.min(100, Number(m[1])); break; }
  }
  const ready = lines.filter((l) => /clip \d+ ready/i.test(String(l))).length;
  return { stage, percent, ready };
}

function mmss(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`;
}

// What a processing project looks like: named steps, the one in progress moving,
// a running clock, and a plain sentence about why it takes the time it takes.
// Nothing here is invented progress: the bar is determinate only when the
// pipeline reported a percentage, and otherwise it just says "working".
export default function JobProgress({ logs, startedAt }) {
  const { t } = useLang();
  const [now, setNow] = useState(() => Date.now());
  const [mountedAt] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const { stage, percent, ready } = useMemo(() => readProgress(logs), [logs]);
  const started = startedAt ? startedAt * 1000 : mountedAt;
  const elapsed = (now - started) / 1000;
  const current = stage < 0 ? 0 : stage;
  const waiting = stage < 0;
  const determinate = STAGES[current].id === 'transcribe' && percent != null;

  return (
    <div className="space-y-5" role="status" aria-live="polite">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-ink">
          {waiting ? t('progress.queued') : t(`progress.${STAGES[current].id}`)}
        </p>
        <span className="readout inline-flex items-center gap-1.5 shrink-0">
          <Clock size={12} /> {mmss(elapsed)}
        </span>
      </div>

      <div className="h-2 rounded-full bg-paper3 overflow-hidden relative" aria-hidden="true">
        {determinate ? (
          <div className="h-full rounded-full bg-brass transition-all duration-700" style={{ width: `${Math.max(percent, 3)}%` }} />
        ) : (
          <div className="indeterminate-bar h-full w-full" />
        )}
      </div>
      {determinate && (
        <p className="text-xs text-muted -mt-2">{t('progress.percent', { n: percent })}</p>
      )}

      <ol className="space-y-3">
        {STAGES.map((s, i) => {
          const Icon = s.icon;
          const done = !waiting && i < current;
          const active = !waiting && i === current;
          return (
            <li key={s.id} className={`flex items-center gap-3 text-sm ${done || active ? 'text-ink' : 'text-muted opacity-60'}`}>
              <span className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border ${done ? 'bg-ok/15 border-ok/30 text-ok' : active ? 'bg-brass/10 border-brass/40 text-brass' : 'border-rule'}`}>
                {done ? <Check size={15} /> : active ? <Loader2 size={15} className="animate-spin" /> : <Icon size={15} />}
              </span>
              <span className="min-w-0">
                {t(`progress.${s.id}`)}
                {s.id === 'render' && ready > 0 && (
                  <span className="text-muted"> · {t('progress.ready', { n: ready })}</span>
                )}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="text-xs text-muted leading-relaxed border-t border-rule pt-4">
        {t(waiting ? 'progress.hint.queued' : `progress.hint.${STAGES[current].id}`)}
      </p>
    </div>
  );
}
