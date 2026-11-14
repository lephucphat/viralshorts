import { useCallback, useEffect, useState } from 'react';
import { Check, X, ArrowRight, Loader2 } from 'lucide-react';
import { useLang } from '../contexts/LangContext';
import { onboardingApi, recoveryApi } from '../lib/studio';

// The Upload-Post key is stored in this browser (App.jsx), so the server cannot see it.
// When it is there, tell the server once; the step then stays ticked on every device.
function hasSocialKey() {
  try { return !!localStorage.getItem('uploadPostKey_v3'); } catch (_) { return false; }
}

/**
 * First-run checklist for the projects page. Everything but "pricing" and "social" is derived
 * on the server from real data (studio/onboarding.py), so a step un-ticks if its data goes away.
 *
 * Props: refreshKey (change it to re-read, e.g. the project count), firstProjectId (the
 * link target of the social step), onCreateClip (focus the link box).
 */
export default function OnboardingChecklist({ refreshKey, firstProjectId, onCreateClip }) {
  const { t } = useLang();
  const [state, setState] = useState(null);       // null until loaded; stays null on error (no checklist)
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState('');

  const load = useCallback(async () => {
    try {
      let s = await onboardingApi.get();
      if (hasSocialKey() && s.steps.some((x) => x.id === 'social' && !x.done)) s = await onboardingApi.report('social');
      setState(s);
    } catch (_) { /* a failed checklist must never get in the way of the page */ }
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);

  if (!state || state.dismissed || state.complete) return null;

  const dismiss = async () => {
    setBusy('dismiss');
    try { setState(await onboardingApi.dismiss()); } catch (_) { setBusy(''); }
  };

  const resend = async () => {
    setBusy('resend');
    try { await recoveryApi.resend(); setSent(true); } catch (_) { /* shown as not sent */ } finally { setBusy(''); }
  };

  const action = (step) => {
    switch (step.id) {
      case 'verify_email':
        return sent
          ? <span className="text-xs text-ok">{t('onb.verify_email.sent')}</span>
          : <button type="button" className="btn-secondary !px-4 !py-1.5 !text-xs" disabled={busy === 'resend'} onClick={resend}>
            {busy === 'resend' && <Loader2 size={13} className="animate-spin" />} {t('onb.verify_email.a')}
          </button>;
      case 'brand_kit':
        return <a href="#/brand" className="btn-secondary !px-4 !py-1.5 !text-xs no-underline">{t('onb.go')} <ArrowRight size={13} /></a>;
      case 'first_clip':
        return <button type="button" className="btn-primary !px-4 !py-1.5 !text-xs" onClick={onCreateClip}>{t('onb.go')} <ArrowRight size={13} /></button>;
      case 'social':
        return firstProjectId
          ? <a href={`#/project/${firstProjectId}`} className="btn-secondary !px-4 !py-1.5 !text-xs no-underline">{t('onb.go')} <ArrowRight size={13} /></a>
          : <span className="text-xs text-muted">{t('onb.social.wait')}</span>;
      case 'pricing':
        return <a href="#/pricing" className="btn-secondary !px-4 !py-1.5 !text-xs no-underline">{t('onb.go')} <ArrowRight size={13} /></a>;
      default:
        return null;
    }
  };

  const pct = Math.round((state.done / state.total) * 100);

  return (
    <section className="card p-5 sm:p-6 max-w-3xl mx-auto" aria-labelledby="onb-title">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 id="onb-title" className="font-display text-xl text-ink">{t('onb.title')}</h2>
          <p className="text-sm text-muted mt-0.5">{t('onb.progress', { done: state.done, total: state.total })}</p>
        </div>
        <button type="button" onClick={dismiss} disabled={busy === 'dismiss'} aria-label={t('onb.dismiss')} title={t('onb.dismiss')}
          className="p-2 -mr-2 -mt-1 rounded-full text-muted hover:text-ink hover:bg-paper3 transition-colors shrink-0">
          <X size={16} />
        </button>
      </div>
      <div className="mt-3 h-1.5 rounded-full bg-paper3 overflow-hidden" role="progressbar" aria-valuemin={0} aria-valuemax={100}
        aria-valuenow={pct} aria-label={t('onb.progress', { done: state.done, total: state.total })}>
        <div className="h-full rounded-full bg-brand transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
      <ul className="mt-4 divide-y divide-rule list-none p-0 m-0">
        {state.steps.map((step) => (
          <li key={step.id} className="flex items-center gap-3 py-3">
            <span className={`w-6 h-6 rounded-full shrink-0 flex items-center justify-center border ${
              step.done ? 'bg-ok/15 border-ok/40 text-ok' : 'border-rule-2 text-transparent'}`}>
              <Check size={14} aria-hidden="true" />
              <span className="sr-only">{step.done ? t('onb.done') : ''}</span>
            </span>
            <div className="min-w-0 flex-1">
              <p className={`text-sm font-medium ${step.done ? 'text-muted line-through' : 'text-ink'}`}>{t(`onb.${step.id}.t`)}</p>
              {!step.done && <p className="text-xs text-muted mt-0.5">{t(`onb.${step.id}.d`)}</p>}
            </div>
            {!step.done && <div className="shrink-0">{action(step)}</div>}
          </li>
        ))}
      </ul>
    </section>
  );
}
