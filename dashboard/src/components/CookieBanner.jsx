// The consent banner. Small on purpose — it is a legal control, not a feature.
//
// Two rules it exists to satisfy:
//   1. Nothing non-essential runs before the visitor agrees. index.html only publishes
//      window.__osAnalyticsInit; lib/consent.js calls it once the `analytics` category is
//      granted, and the tracker also stays silent unless the operator set the
//      VITE_OPENPANEL_* variables at build time.
//   2. Refusing must cost exactly as much as accepting. "Reject all" and "Accept all" are
//      the same component with the same size, weight, colour and position; there is no
//      pre-ticked optional box and no dark pattern.
//
// It renders nothing once a decision exists — the "Cookie" link in the landing footer
// (openConsentManager) is how anyone changes their mind. Text is bilingual (vi/en) via
// the i18n dictionary, keys `cookie.*`.
import { useEffect, useState } from 'react';
import {
  getConsent, hasDecided, acceptAll, rejectAll, setConsent,
  onConsentOpenRequest,
} from '../lib/consent';
import { useLang } from '../contexts/LangContext';

const CATEGORIES = [
  { key: 'necessary', locked: true },
  { key: 'analytics' },
  { key: 'marketing' },
];

export default function CookieBanner() {
  const { t } = useLang();
  const [open, setOpen] = useState(() => !hasDecided());
  const [details, setDetails] = useState(false);
  const [draft, setDraft] = useState(() => getConsent());

  useEffect(() => onConsentOpenRequest(() => {
    setDraft(getConsent());
    setDetails(true);
    setOpen(true);
  }), []);

  if (!open) return null;

  const close = () => { setOpen(false); setDetails(false); };

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label={t('cookie.aria')}
      className="fixed inset-x-0 bottom-0 z-50 p-3 sm:p-4 pb-[max(0.75rem,env(safe-area-inset-bottom))]"
    >
      <div className="card mx-auto max-w-3xl p-4 sm:p-5 space-y-4 shadow-2xl">
        <div className="space-y-2">
          <h2 className="font-display lowercase text-lg text-ink">{t('cookie.title')}</h2>
          <p className="text-sm text-ink2">
            {t('cookie.intro')}{' '}
            <a href="/privacy" className="underline hover:text-ink">{t('cookie.policy')}</a>.
          </p>
        </div>

        {details && (
          <ul className="space-y-3 border-t border-rule pt-3">
            {CATEGORIES.map((cat) => (
              <li key={cat.key} className="flex gap-3">
                <input
                  type="checkbox"
                  id={`consent-${cat.key}`}
                  className="mt-1 h-4 w-4 shrink-0 accent-current"
                  checked={cat.locked ? true : !!draft[cat.key]}
                  disabled={cat.locked}
                  onChange={(e) => setDraft({ ...draft, [cat.key]: e.target.checked })}
                />
                <label htmlFor={`consent-${cat.key}`} className="text-sm">
                  <span className="text-ink">{t(`cookie.${cat.key}.label`)}</span>
                  {cat.locked && <span className="text-muted"> · {t('cookie.always')}</span>}
                  <span className="block text-muted">{t(`cookie.${cat.key}.body`)}</span>
                </label>
              </li>
            ))}
          </ul>
        )}

        <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
          {/* Reject and Accept are deliberately the same button. */}
          <button
            type="button"
            className="btn-ghost flex-1"
            onClick={() => { rejectAll(); close(); }}
          >
            {t('cookie.reject')}
          </button>
          <button
            type="button"
            className="btn-ghost flex-1"
            onClick={() => { acceptAll(); close(); }}
          >
            {t('cookie.accept')}
          </button>
          {details ? (
            <button
              type="button"
              className="btn-quiet sm:w-auto"
              onClick={() => { setConsent(draft); close(); }}
            >
              {t('cookie.save')}
            </button>
          ) : (
            <button
              type="button"
              className="btn-quiet sm:w-auto"
              onClick={() => setDetails(true)}
            >
              {t('cookie.choose')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
