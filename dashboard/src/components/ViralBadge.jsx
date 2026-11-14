import React, { useEffect, useRef, useState } from 'react';
import { TrendingUp, X } from 'lucide-react';
import { useT } from '../contexts/LangContext';

// Order the signals are listed in the popover; unknown keys from a newer
// backend are simply not shown.
const SIGNALS = ['llm', 'hook', 'pace', 'silence', 'length', 'audio'];

function tone(score) {
    if (score >= 80) return 'text-ok';
    if (score >= 65) return 'text-brass';
    return 'text-ink2';
}

function barTone(value) {
    if (value >= 80) return 'bg-ok';
    if (value >= 55) return 'bg-brass';
    return 'bg-muted';
}

// "viral N/100" pill. When the backend sent the explainable breakdown
// (viral_scoring.py) the pill opens a small panel saying why; clips from older
// jobs only carry predicted_score and render as a plain, non-interactive pill.
export default function ViralBadge({ clip }) {
    const t = useT();
    const [open, setOpen] = useState(false);
    const rootRef = useRef(null);

    const hasViral = Number.isFinite(clip?.viral_score);
    const score = hasViral ? clip.viral_score : clip?.predicted_score;
    const breakdown = hasViral && clip.viral_breakdown && typeof clip.viral_breakdown === 'object'
        ? clip.viral_breakdown : null;
    const reasons = Array.isArray(clip?.viral_reasons) ? clip.viral_reasons : [];
    const interactive = Boolean(breakdown);

    useEffect(() => {
        if (!open) return undefined;
        const onDown = (e) => {
            if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
        };
        const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
        document.addEventListener('mousedown', onDown);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onDown);
            document.removeEventListener('keydown', onKey);
        };
    }, [open]);

    if (!Number.isFinite(score)) return null;

    const pill = (
        <>
            <TrendingUp size={11} className="shrink-0 text-muted" />
            <span className="text-muted">{t('viral.label')}</span>
            <b className={tone(score)}>{score}</b>
            <span className="text-muted">/100</span>
        </>
    );
    const pillClass = 'bg-black/70 font-mono text-micro uppercase px-2 py-1 rounded-full flex items-center gap-1';

    if (!interactive) {
        return (
            <span className={pillClass} title={t('viral.titleNoDetail')}>
                {pill}
            </span>
        );
    }

    return (
        <div ref={rootRef} className="relative">
            <button
                type="button"
                className={`${pillClass} hover:bg-black/85 transition-colors cursor-pointer`}
                title={t('viral.title')}
                aria-expanded={open}
                onClick={() => setOpen((v) => !v)}
            >
                {pill}
            </button>

            {open && (
                <div
                    role="dialog"
                    aria-label={t('viral.breakdown')}
                    className="absolute left-0 top-full mt-2 z-30 w-64 rounded-input border border-rule bg-paper2 p-3 shadow-lg normal-case"
                >
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-ink">{t('viral.breakdown')}</span>
                        <button
                            type="button"
                            className="text-muted hover:text-ink"
                            aria-label={t('viral.close')}
                            onClick={() => setOpen(false)}
                        >
                            <X size={14} />
                        </button>
                    </div>

                    <ul className="space-y-2">
                        {SIGNALS.filter((k) => Number.isFinite(breakdown[k])).map((k) => (
                            <li key={k}>
                                <div className="flex justify-between text-[0.6875rem] text-ink2 mb-0.5">
                                    <span>{t(`viral.signal.${k}`)}</span>
                                    <span className="font-mono">{breakdown[k]}</span>
                                </div>
                                <div className="h-1 rounded-full bg-paper3 overflow-hidden">
                                    <div
                                        className={`h-full ${barTone(breakdown[k])}`}
                                        style={{ width: `${Math.max(0, Math.min(100, breakdown[k]))}%` }}
                                    />
                                </div>
                            </li>
                        ))}
                    </ul>

                    {reasons.length > 0 && (
                        <ul className="mt-3 pt-2 border-t border-rule space-y-1 text-[0.6875rem] text-ink2">
                            {reasons.map((code) => (
                                <li key={code}>• {t(`viral.reason.${code}`)}</li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}
