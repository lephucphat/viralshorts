import { useEffect, useId, useMemo, useState } from 'react';
import { Check, Loader2, Minus, Sparkles, Mail } from 'lucide-react';
import StudioShell from '../StudioShell';
import { useLang } from '../contexts/LangContext';
import { useAuth } from '../contexts/AuthContext';
import { billingApi, onboardingApi } from '../lib/studio';
import { errorMessage } from '../lib/errors';
import { SUPPORT_EMAIL } from '../../seo/site.js';

// What a plan includes, in the order people look for it. Everything is read from
// /api/billing/plans (studio/plans.py), so this page cannot disagree with the server.
const FEATURE_ORDER = ['clips', 'subtitles', 'hooks', 'thumbnails', 'effects', 'dubbing', 'publish', 'api_access'];
const EXTRA_FEATURES = ['brand_kits', 'priority_support'];   // only the Business plan lists these
const COST_ORDER = ['process_per_minute', 'analysis', 'transcribe', 'subtitles', 'hook', 'render', 'thumbnails',
  'dubbing_per_minute'];
const FAQ = [1, 2, 3, 4, 5, 6];
const hasRealEmail = !SUPPORT_EMAIL.startsWith('[');

// Prices arrive as integers in the minor unit of the provider's currency:
// US cents for Stripe, whole dong for PayOS.
function money(amount, provider, lang) {
  if (amount == null) return null;
  return provider === 'payos'
    ? new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(amount)
    : new Intl.NumberFormat(lang === 'vi' ? 'vi-VN' : 'en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: amount % 100 ? 2 : 0 }).format(amount / 100);
}

const priceOf = (item, provider, period) => {
  const suffix = period === 'year' ? '_yearly' : '';
  return provider === 'payos' ? item[`price_vnd${suffix}`] : item[`price_usd_cents${suffix}`];
};

const featureLabel = (t, f) => (EXTRA_FEATURES.includes(f) ? t(`pr.feat.${f}`) : t(`billing.feat.${f}`));

function Cell({ yes, t }) {
  return yes
    ? <><Check size={16} className="text-ok mx-auto" aria-hidden="true" /><span className="sr-only">{t('pr.compare.yes')}</span></>
    : <><Minus size={16} className="text-muted/60 mx-auto" aria-hidden="true" /><span className="sr-only">{t('pr.compare.no')}</span></>;
}

function CreditCalculator({ catalog, t, lang }) {
  const [source, setSource] = useState('60');
  const [dub, setDub] = useState('0');
  const srcId = useId();
  const dubId = useId();
  const num = (v) => Math.min(100000, Math.max(0, Math.ceil(Number(v) || 0)));
  const perMin = catalog.costs.process_per_minute ?? 1;
  const dubPerMin = catalog.costs.dubbing_per_minute ?? 0;
  const need = perMin * num(source) + dubPerMin * num(dub);
  const byCredits = [...catalog.plans].sort((a, b) => a.credits - b.credits);
  const fit = byCredits.find((p) => p.credits >= need);
  const fmt = (n) => n.toLocaleString(lang === 'vi' ? 'vi-VN' : 'en-US');

  return (
    <section className="mt-14" aria-labelledby="calc-title">
      <h2 id="calc-title" className="font-display text-2xl text-ink">{t('pr.calc.title')}</h2>
      <p className="text-sm text-muted mt-1">{t('pr.calc.sub')}</p>
      <div className="mt-5 card p-5 sm:p-6 grid md:grid-cols-2 gap-8 items-center">
        <div className="space-y-5">
          <div>
            <label htmlFor={srcId} className="block text-sm text-ink2 mb-1.5">{t('pr.calc.source')}</label>
            <div className="flex items-center gap-3">
              <input type="range" min="0" max="600" step="5" value={Math.min(600, num(source))} aria-label={t('pr.calc.source')}
                onChange={(e) => setSource(e.target.value)} className="flex-1 accent-brass" />
              <input id={srcId} type="number" inputMode="numeric" min="0" max="100000" value={source}
                onChange={(e) => setSource(e.target.value)} className="input-field !w-24 !py-2 text-right tabular-nums" />
            </div>
          </div>
          {dubPerMin > 0 && (
            <div>
              <label htmlFor={dubId} className="block text-sm text-ink2 mb-1.5">{t('pr.calc.dub')}</label>
              <input id={dubId} type="number" inputMode="numeric" min="0" max="100000" value={dub}
                onChange={(e) => setDub(e.target.value)} className="input-field !w-28 !py-2 text-right tabular-nums" />
            </div>
          )}
        </div>
        <div className="rounded-2xl bg-paper3/60 p-5 text-center md:text-left" role="status" aria-live="polite">
          <p className="text-sm text-muted">{t('pr.calc.need')}</p>
          <p className="font-display text-3xl text-ink mt-1 tabular-nums">
            <span className="text-gradient">{t('pr.calc.credits', { n: fmt(need) })}</span>
          </p>
          {need > 0 && (
            <p className="text-sm text-ink2 mt-3">
              {!fit && t('pr.calc.over')}
              {fit && (fit.id === 'free' ? t('pr.calc.fit_free') : t('pr.calc.fit', { plan: fit.name }))}
            </p>
          )}
        </div>
      </div>
      <p className="text-xs text-muted mt-3">{t('pr.calc.note')}</p>
    </section>
  );
}

function CompareTable({ plans, t, lang }) {
  const fmt = (n) => n.toLocaleString(lang === 'vi' ? 'vi-VN' : 'en-US');
  const features = [...FEATURE_ORDER, ...EXTRA_FEATURES].filter((f) => plans.some((p) => p.features.includes(f)));
  const rows = [
    ['credits', t('pr.compare.credits'), (p) => (p.contact ? `${fmt(p.credits)}+` : fmt(p.credits))],
    ['jobs', t('pr.compare.jobs'), (p) => p.max_active_jobs],
    ['retention', t('pr.compare.retention'), (p) => t('pr.compare.days', { n: p.retention_days })],
  ];
  return (
    <section className="mt-14" aria-labelledby="compare-title">
      <h2 id="compare-title" className="font-display text-2xl text-ink">{t('pr.compare.title')}</h2>
      <p className="text-sm text-muted mt-1">{t('pr.compare.sub')}</p>
      <div className="mt-5 card relative overflow-x-auto custom-scrollbar">
        <table className="w-full min-w-[640px] text-sm border-collapse">
          <thead>
            <tr className="border-b border-rule">
              <th scope="col" className="sticky left-0 z-10 bg-paper2 text-left font-medium text-muted px-4 py-3 w-[34%]">{t('pr.compare.feature')}</th>
              {plans.map((p) => <th key={p.id} scope="col" className="px-3 py-3 font-display text-base text-ink text-center">{p.name}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {rows.map(([id, label, render]) => (
              <tr key={id}>
                <th scope="row" className="sticky left-0 z-10 bg-paper2 text-left font-normal text-ink2 px-4 py-3">{label}</th>
                {plans.map((p) => <td key={p.id} className="px-3 py-3 text-center text-ink tabular-nums">{render(p)}</td>)}
              </tr>
            ))}
            {features.map((f) => (
              <tr key={f}>
                <th scope="row" className="sticky left-0 z-10 bg-paper2 text-left font-normal text-ink2 px-4 py-3">{featureLabel(t, f)}</th>
                {plans.map((p) => <td key={p.id} className="px-3 py-3 text-center"><Cell yes={p.features.includes(f)} t={t} /></td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function StudioPricingPage() {
  const { t, lang } = useLang();
  const { usage } = useAuth();
  const [catalog, setCatalog] = useState(null);
  const [error, setError] = useState('');
  const [provider, setProvider] = useState('');
  const [period, setPeriod] = useState('month');   // 'month' | 'year'
  const [busy, setBusy] = useState('');     // "<kind>:<item>" while a checkout is being created

  const notice = useMemo(() => {
    const q = (window.location.hash.split('?')[1] || '');
    return new URLSearchParams(q).get('checkout') === 'cancelled' ? t('billing.cancelled') : '';
  }, [t]);

  useEffect(() => {
    let live = true;
    billingApi.plans()
      .then((c) => { if (live) { setCatalog(c); setProvider((p) => p || c.providers[0] || (lang === 'vi' ? 'payos' : 'stripe')); } })
      .catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [lang]);

  // Opening this page ticks the "look at the plans" step of the first-run checklist.
  useEffect(() => { onboardingApi.report('pricing').catch(() => { /* a checklist tick is never worth an error */ }); }, []);

  const currentPlan = usage?.plan || 'free';
  const rank = (id) => (catalog ? catalog.plans.findIndex((p) => p.id === id) : 0);

  const buy = async (kind, item) => {
    setBusy(`${kind}:${item}`); setError('');
    try {
      const res = await billingApi.checkout({ kind, item, provider, ...(kind === 'subscription' && period === 'year' ? { interval: 'year' } : {}) });
      window.location.assign(res.url);      // the provider's page; we come back to #/account
    } catch (e) {
      setError(errorMessage(t, e, { checkout_failed: 'billing.err.checkout_failed' }));
      setBusy('');
    }
  };

  const free = catalog?.plans.find((p) => !p.price_usd_cents && !p.price_vnd);
  const paid = catalog ? catalog.plans.filter((p) => p.price_usd_cents || p.price_vnd) : [];
  const contact = catalog?.contact_plans || [];
  const shown = [free, ...paid, ...contact].filter(Boolean);
  const yearly = period === 'year';
  const yearlyBlocked = yearly && !catalog?.yearly_checkout;
  const saveMonths = paid[0]?.yearly_discount_months || 0;

  return (
    <StudioShell active="pricing" wide>
      <header className="max-w-3xl mb-8">
        <p className="eyebrow">{t('billing.eyebrow')}</p>
        <h1 className="font-display text-3xl sm:text-4xl text-ink mt-1">{t('pr.title')}</h1>
        <p className="text-ink2 mt-2">{t('pr.sub')}</p>
      </header>

      {notice && <p role="status" className="text-sm text-ink2 bg-paper3 rounded-input px-3 py-2 mb-6 max-w-3xl">{notice}</p>}
      {error && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3 py-2 mb-6 max-w-3xl">{error}</p>}
      {!catalog && !error && <Loader2 size={20} className="animate-spin text-muted" />}

      {catalog?.prices_placeholder && (
        <p role="note" className="text-sm text-warn bg-warn/10 rounded-input px-3 py-2 mb-6 max-w-3xl">{t('pr.placeholder')}</p>
      )}
      {catalog && catalog.providers.length === 0 && (
        <p className="text-sm text-warn bg-warn/10 rounded-input px-3 py-2 mb-6 max-w-3xl">{t('billing.off')}</p>
      )}

      {catalog && (
        <div className="mb-8 flex flex-wrap items-center gap-x-6 gap-y-3">
          <div role="group" aria-label={t('pr.billing')} className="inline-flex rounded-full border border-rule-2 p-0.5 bg-paper2">
            {['month', 'year'].map((p) => (
              <button key={p} type="button" onClick={() => setPeriod(p)} aria-pressed={period === p}
                className={`px-5 py-2 rounded-full text-sm transition-colors ${period === p ? 'bg-brand text-brassink shadow-cta font-semibold' : 'text-ink2 hover:text-ink'}`}>
                {t(p === 'month' ? 'pr.monthly' : 'pr.yearly')}
                {p === 'year' && saveMonths > 0 && <span className={`ml-2 text-xs ${period === 'year' ? 'opacity-90' : 'text-brass'}`}>{t('pr.save', { n: saveMonths })}</span>}
              </button>
            ))}
          </div>
          {catalog.providers.length > 1 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted mr-1">{t('billing.pay.with')}</span>
              {catalog.providers.map((p) => (
                <button key={p} type="button" onClick={() => setProvider(p)} aria-pressed={provider === p} className="chip">
                  {t(`billing.pay.${p}`)}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      {yearlyBlocked && <p className="text-sm text-muted -mt-4 mb-8">{t('pr.yearly.off')}</p>}

      {catalog && (
        <>
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-5 items-stretch">
            {shown.map((plan) => {
              const isContact = !!plan.contact;
              const isCurrent = plan.id === currentPlan;
              const amount = isContact ? null : priceOf(plan, provider, period);
              const perMonth = amount != null && yearly ? Math.round(amount / 12) : amount;
              const featured = plan.id === 'pro';
              const isPaid = !isContact && plan.id !== free?.id;
              return (
                <section key={plan.id} className={`card p-6 flex flex-col ${featured ? 'ring-1 ring-brass shadow-pop' : ''}`}>
                  <div className="flex items-center justify-between">
                    <h2 className="font-display text-xl text-ink">{plan.name}</h2>
                    {featured && <span className="badge-brass flex items-center gap-1"><Sparkles size={13} /> {t('billing.popular')}</span>}
                  </div>
                  {isContact ? (
                    <>
                      <p className="mt-3 text-3xl font-display text-ink">{t('pr.business.price')}</p>
                      <p className="text-sm text-ink2 mt-1">{t('pr.business.credits', { n: plan.credits.toLocaleString(lang === 'vi' ? 'vi-VN' : 'en-US') })}</p>
                    </>
                  ) : (
                    <>
                      <p className="mt-3 text-3xl font-display text-ink tabular-nums">
                        {money(perMonth || 0, provider, lang)}
                        <span className="text-sm text-muted font-sans"> {t('pr.per_month')}</span>
                      </p>
                      <p className="text-xs text-muted mt-1 min-h-[1rem]">
                        {yearly && isPaid && amount ? t('pr.billed_year', { amount: money(amount, provider, lang) }) : ''}
                      </p>
                      <p className="text-sm text-ink2 mt-1">{t('billing.credits_month', { n: plan.credits.toLocaleString(lang === 'vi' ? 'vi-VN' : 'en-US') })}</p>
                    </>
                  )}
                  <ul className="mt-5 space-y-2 text-sm text-ink2 flex-1">
                    <li className="flex gap-2"><Check size={15} className="text-ok mt-0.5 shrink-0" />{t('billing.jobs', { n: plan.max_active_jobs })}</li>
                    <li className="flex gap-2"><Check size={15} className="text-ok mt-0.5 shrink-0" />{t('billing.retention', { n: plan.retention_days })}</li>
                    {[...FEATURE_ORDER, ...EXTRA_FEATURES].filter((f) => plan.features.includes(f)).map((f) => (
                      <li key={f} className="flex gap-2"><Check size={15} className="text-ok mt-0.5 shrink-0" />{featureLabel(t, f)}</li>
                    ))}
                  </ul>
                  <div className="mt-6">
                    {isContact && (
                      <a className="btn-secondary w-full py-2.5 no-underline"
                        href={hasRealEmail ? `mailto:${SUPPORT_EMAIL}?subject=Business` : '/legal-notice'}>
                        <Mail size={15} /> {t('pr.business.cta')}
                      </a>
                    )}
                    {!isContact && isCurrent && (
                      <div className="text-center py-1">
                        <span className="block text-sm text-muted">{t('billing.plan.current')}</span>
                        {plan.id !== 'free' && <a href="#/account" className="text-sm text-brass hover:underline">{t('billing.plan.manage')}</a>}
                      </div>
                    )}
                    {!isContact && !isCurrent && isPaid && (
                      <button type="button" className="btn-primary w-full py-2.5"
                        disabled={!catalog.providers.length || !!busy || yearlyBlocked || rank(plan.id) < rank(currentPlan)}
                        title={yearlyBlocked ? t('pr.yearly.unavailable') : rank(plan.id) < rank(currentPlan) ? t('billing.plan.downgrade') : undefined}
                        onClick={() => buy('subscription', plan.id)}>
                        {busy === `subscription:${plan.id}` && <Loader2 size={15} className="animate-spin" />}{' '}
                        {t(rank(plan.id) > rank(currentPlan) && currentPlan !== 'free' ? 'billing.plan.upgrade' : 'billing.plan.choose')}
                      </button>
                    )}
                  </div>
                </section>
              );
            })}
          </div>

          {provider === 'payos' && <p className="text-xs text-muted mt-3">{t('billing.payos.note')}</p>}

          <CompareTable plans={shown} t={t} lang={lang} />
          <CreditCalculator catalog={catalog} t={t} lang={lang} />

          <section className="mt-14 grid lg:grid-cols-2 gap-8">
            <div>
              <h2 className="font-display text-xl text-ink">{t('billing.topup.title')}</h2>
              <p className="text-sm text-muted mt-1">{t('billing.topup.sub')}</p>
              <div className="mt-4 space-y-3">
                {catalog.packs.map((pack) => {
                  const price = money(priceOf(pack, provider, 'month'), provider, lang);
                  return (
                    <div key={pack.id} className="card p-4 flex items-center justify-between gap-4">
                      <div>
                        <p className="text-ink font-medium tabular-nums">{t('billing.credits_n', { n: pack.credits.toLocaleString(lang === 'vi' ? 'vi-VN' : 'en-US') })}</p>
                        <p className="text-sm text-muted">{price}</p>
                      </div>
                      <button type="button" className="btn-secondary !px-4 !py-2" disabled={!catalog.providers.length || !!busy}
                        onClick={() => buy('topup', pack.id)}>
                        {busy === `topup:${pack.id}` && <Loader2 size={15} className="animate-spin" />} {t('billing.topup.buy')}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            <div>
              <h2 className="font-display text-xl text-ink">{t('billing.costs.title')}</h2>
              <p className="text-sm text-muted mt-1">{t('billing.costs.sub')}</p>
              <dl className="mt-4 card divide-y divide-rule">
                {COST_ORDER.filter((k) => catalog.costs[k] != null).map((k) => (
                  <div key={k} className="flex items-center justify-between px-4 py-3 text-sm">
                    <dt className="text-ink2">{t(`billing.cost.${k}`)}</dt>
                    <dd className="readout">{catalog.costs[k]}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </section>

          <section className="mt-14 max-w-3xl">
            <h2 className="font-display text-xl text-ink">{t('billing.faq.title')}</h2>
            <div className="mt-4 card divide-y divide-rule">
              {FAQ.map((n) => (
                <details key={n} className="group px-4 py-3">
                  <summary className="cursor-pointer text-ink text-sm font-medium list-none flex justify-between gap-3">
                    {t(n === 6 ? 'pr.faq.q6' : `billing.faq.q${n}`)}
                    <span className="text-muted group-open:rotate-45 transition-transform" aria-hidden="true">+</span>
                  </summary>
                  <p className="text-sm text-ink2 mt-2">
                    {t(n === 6 ? 'pr.faq.a6' : `billing.faq.a${n}`)}
                    {n === 5 && <> <a href="/refunds" target="_blank" rel="noreferrer" className="text-brass hover:underline">{t('billing.faq.refunds')}</a></>}
                  </p>
                </details>
              ))}
            </div>
          </section>
        </>
      )}
    </StudioShell>
  );
}
