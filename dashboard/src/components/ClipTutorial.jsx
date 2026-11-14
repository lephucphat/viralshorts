import { useEffect, useLayoutEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, LayoutDashboard, Sparkles } from 'lucide-react';
import Modal from './ui/Modal';
import { useT } from '../contexts/LangContext';

const TOUR = [
  {
    target: '[data-tutorial="nav-clips"]',
    titleKey: 'tut.s1.title',
    bodyKey: 'tut.s1.body',
  },
  {
    target: '[data-tutorial="source-tabs"]',
    titleKey: 'tut.s2.title',
    bodyKey: 'tut.s2.body',
  },
  {
    target: '[data-tutorial="drop-zone"]',
    titleKey: 'tut.s3.title',
    bodyKey: 'tut.s3.body',
  },
  {
    target: '[data-tutorial="output-format"]',
    titleKey: 'tut.s4.title',
    bodyKey: 'tut.s4.body',
  },
  {
    target: '[data-tutorial="generate"]',
    titleKey: 'tut.s5.title',
    bodyKey: 'tut.s5.body',
  },
];

function visibleTarget(selector) {
  return [...document.querySelectorAll(selector)].find((el) => {
    const r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  }) || null;
}

function placeTip(rect, tipW, tipH, vw, vh) {
  const m = 12;
  const gap = 12;
  const mobile = vw < 640;
  if (mobile) {
    return {
      top: Math.max(m, vh - tipH - m - 8),
      left: m,
      width: vw - m * 2,
    };
  }
  let top = rect.bottom + gap;
  if (top + tipH > vh - m) top = rect.top - gap - tipH;
  if (top < m) top = m;
  let left = rect.left + rect.width / 2 - tipW / 2;
  left = Math.max(m, Math.min(left, vw - m - tipW));
  return { top, left, width: tipW };
}

/**
 * First-login Clip Generator tutorial.
 *  - intro: blocking modal
 *  - coach: Next/Back spotlight on each Clip Generator control
 *  - celebrate: modal after the first successful job
 *
 * QA: #app?tutorial=1
 */
export default function ClipTutorial({ phase, jobStatus, onStart, onSkip, onDismissCelebrate }) {
  const t = useT();
  const [step, setStep] = useState(0);
  const [spot, setSpot] = useState(null);

  useEffect(() => {
    if (phase === 'coach') setStep(0);
  }, [phase]);

  useLayoutEffect(() => {
    if (phase !== 'coach' || jobStatus === 'processing' || jobStatus === 'error') {
      setSpot(null);
      return;
    }
    const measure = () => {
      const spec = TOUR[step];
      if (!spec) { setSpot(null); return; }
      const el = visibleTarget(spec.target);
      if (el) el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      const rect = el ? el.getBoundingClientRect() : null;
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const r = (n) => Math.round(n);
      const mobile = vw < 640;
      const tipW = Math.min(360, vw - 24);
      const tipH = 220;
      const hole = rect
        ? { top: r(rect.top - 6), left: r(rect.left - 6), width: r(rect.width + 12), height: r(rect.height + 12) }
        : null;
      const rawTip = hole
        ? placeTip({ top: hole.top, bottom: hole.top + hole.height, left: hole.left, width: hole.width }, tipW, tipH, vw, vh)
        : { top: mobile ? vh - 240 : vh / 2 - 80, left: 12, width: vw - 24 };
      const tip = { top: r(rawTip.top), left: r(rawTip.left), width: r(rawTip.width) };
      setSpot((prev) => {
        const next = { hole, tip, mobile };
        try {
          if (prev && JSON.stringify(prev) === JSON.stringify(next)) return prev;
        } catch (_) { /* ignore */ }
        return next;
      });
    };
    measure();
    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, true);
    return () => {
      window.removeEventListener('resize', measure);
      window.removeEventListener('scroll', measure, true);
    };
  }, [phase, step, jobStatus]);

  if (phase === 'intro') {
    return (
      <Modal isOpen hideClose eyebrow={t('tut.eyebrow')} title={t('tut.intro.title')} size="md">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-input bg-paper3 flex items-center justify-center shrink-0">
            <LayoutDashboard size={18} className="text-brass" />
          </div>
          <p className="text-sm text-ink2 leading-relaxed">
            {t('tut.intro.body')}
          </p>
        </div>
        <button type="button" onClick={onStart} className="btn-primary w-full">
          {t('tut.show')} <ArrowRight size={16} />
        </button>
        <button
          type="button"
          onClick={onSkip}
          className="w-full mt-2 text-muted hover:text-ink text-sm lowercase py-2 transition-colors"
        >
          {t('tut.later')}
        </button>
      </Modal>
    );
  }

  if (phase === 'coach' && (jobStatus === 'processing' || jobStatus === 'error')) {
    return (
      <div
        className="fixed z-[80] left-3 right-3 md:left-auto md:right-6 md:w-[22rem]
          bottom-3 md:bottom-6 card p-4"
        role="status"
      >
        <p className="eyebrow mb-2">{t('tut.coach.eyebrow')}</p>
        <p className={`text-sm leading-relaxed ${jobStatus === 'error' ? 'text-danger' : 'text-muted'}`}>
          {jobStatus === 'error'
            ? t('tut.failed')
            : t('tut.wait')}
        </p>
      </div>
    );
  }

  if (phase === 'coach') {
    const last = step >= TOUR.length - 1;
    const spec = TOUR[step] || TOUR[0];
    const onLast = () => setStep(TOUR.length);

    if (step >= TOUR.length) {
      return (
        <div
          className="fixed z-[80] inset-x-3 bottom-3 md:inset-x-auto md:right-6 md:bottom-6 md:max-w-sm
            card px-4 py-3 flex flex-wrap items-center gap-x-3 gap-y-1"
          role="status"
        >
          <p className="text-sm text-muted leading-snug flex-1 min-w-0">
            {t('tut.turn')}
          </p>
          <button type="button" onClick={onSkip} className="text-xs lowercase text-muted hover:text-ink shrink-0">
            {t('tut.skip')}
          </button>
        </div>
      );
    }

    const hole = spot?.hole;
    const tip = spot?.tip;

    return (
      <div className="fixed inset-0 z-[80]" role="dialog" aria-modal="true" aria-label={t('tut.aria')}>
        {!hole && <div className="absolute inset-0 bg-black/55" />}
        {hole && (
          <div
            className="absolute rounded-input pointer-events-none border border-brass/70"
            style={{
              top: hole.top,
              left: hole.left,
              width: hole.width,
              height: hole.height,
              boxShadow: '0 0 0 9999px rgba(0,0,0,0.55)',
            }}
          />
        )}
        <div
          className="absolute card p-4 max-h-[min(70vh,24rem)] overflow-y-auto"
          style={{
            top: tip?.top ?? 16,
            left: tip?.left ?? 12,
            width: tip?.width ?? undefined,
            maxWidth: 'calc(100vw - 24px)',
          }}
        >
          <p className="eyebrow mb-2">{String(step + 1).padStart(2, '0')} / {String(TOUR.length).padStart(2, '0')}</p>
          <h3 className="font-display lowercase text-lg text-ink leading-tight mb-2">{t(spec.titleKey)}</h3>
          <p className="text-sm text-muted leading-relaxed mb-4">{t(spec.bodyKey)}</p>
          <div className="flex flex-wrap items-center gap-2">
            {step > 0 && (
              <button type="button" onClick={() => setStep((s) => s - 1)} className="btn-ghost text-sm px-3">
                <ArrowLeft size={14} /> {t('tut.back')}
              </button>
            )}
            <button
              type="button"
              onClick={last ? onLast : () => setStep((s) => s + 1)}
              className="btn-primary text-sm px-4 ml-auto"
            >
              {last ? t('tut.got') : t('tut.next')} <ArrowRight size={14} />
            </button>
          </div>
          <button type="button" onClick={onSkip} className="mt-3 text-xs lowercase text-muted hover:text-ink transition-colors">
            {t('tut.skipall')}
          </button>
        </div>
      </div>
    );
  }

  if (phase === 'celebrate') {
    return (
      <Modal isOpen onClose={onDismissCelebrate} hideClose eyebrow={t('tut.done.eyebrow')} title={t('tut.done.title')} size="sm">
        <div className="text-center py-2">
          <div className="inline-flex p-3 bg-paper3 rounded-full text-ok mb-4">
            <CheckCircle2 size={28} />
          </div>
          <p className="text-sm text-ink2 leading-relaxed mb-1">
            {t('tut.done.a')}
          </p>
          <p className="text-sm text-muted leading-relaxed mb-6">
            {t('tut.done.b')}
          </p>
          <button type="button" onClick={onDismissCelebrate} className="btn-primary w-full">
            <Sparkles size={16} /> {t('tut.see')}
          </button>
        </div>
      </Modal>
    );
  }

  return null;
}
