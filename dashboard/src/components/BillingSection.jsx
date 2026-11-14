import { useEffect, useState } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';
import { billingApi } from '../lib/studio';
import { errorMessage } from '../lib/errors';

const dateOf = (epoch, lang) =>
  new Date(epoch * 1000).toLocaleDateString(lang === 'vi' ? 'vi-VN' : 'en-US', { day: 'numeric', month: 'short', year: 'numeric' });

function amountOf(p, lang) {
  if (p.currency?.toLowerCase() === 'vnd') {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(p.amount);
  }
  return new Intl.NumberFormat(lang === 'vi' ? 'vi-VN' : 'en-US', { style: 'currency', currency: (p.currency || 'usd').toUpperCase() })
    .format(p.amount / 100);
}

// The account page's money section: current plan, where the credits come from, the
// payment portal and the history. Rendered only when the server runs the paid edition.
export default function BillingSection() {
  const { t, lang } = useLang();
  const { usage, refreshMe } = useAuth();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const [portalBusy, setPortalBusy] = useState(false);
  const [justPaid, setJustPaid] = useState(false);
  const [planBusy, setPlanBusy] = useState(false);

  useEffect(() => {
    let live = true;
    const arrivedFromCheckout = (window.location.hash.split('?')[1] || '').includes('checkout=success');
    if (arrivedFromCheckout) setJustPaid(true);

    const load = () => billingApi.status().then((s) => live && setStatus(s)).catch((e) => live && setError(e.message));
    load();

    // A bank-transfer order (PayOS): ask the server to confirm it with PayOS right away, so a
    // slow or unreachable webhook does not leave a paying customer looking at the old balance.
    // The code is ours (`order=`) or PayOS's own (`orderCode=`), in the hash or the query string.
    const order = (window.location.href.match(/[?&](?:order|orderCode)=(\d{6,20})/) || [])[1];
    const syncOrder = () => (order
      ? billingApi.syncPayos(order).then(() => { load(); refreshMe(); }).catch(() => {})
      : null);
    if (arrivedFromCheckout) syncOrder();

    // The provider tells our server by webhook, a moment after the browser is back.
    // Look again a few times instead of showing a stale balance.
    const timers = arrivedFromCheckout
      ? [2500, 6000, 12000].map((ms) => setTimeout(() => { syncOrder(); load(); refreshMe(); }, ms))
      : [];
    return () => { live = false; timers.forEach(clearTimeout); };
  }, [refreshMe]);

  const openPortal = async () => {
    setPortalBusy(true); setError('');
    try {
      const res = await billingApi.portal();
      window.location.assign(res.url);
    } catch (e) {
      setError(t('billing.account.manage.error', { error: e.message }));
      setPortalBusy(false);
    }
  };

  const reload = () => billingApi.status().then(setStatus).catch(() => {});

  // Stop (or restart) a card plan renewing; the paid period keeps running either way.
  const setRenewal = async (cancel) => {
    if (cancel && !window.confirm(t('billing.cancel.confirm'))) return;
    setPlanBusy(true); setError('');
    try {
      await (cancel ? billingApi.cancel() : billingApi.resume());
      await reload();
    } catch (e) {
      setError(t('billing.err.cancel', { error: errorMessage(t, e) }));
    } finally { setPlanBusy(false); }
  };

  // A prepaid (PayOS) plan does not renew by itself: buying the same plan again adds a period.
  const renewPrepaid = async () => {
    setPlanBusy(true); setError('');
    try {
      const res = await billingApi.checkout({ kind: 'subscription', item: usage.plan, provider: 'payos' });
      window.location.assign(res.url);
    } catch (e) {
      setError(errorMessage(t, e));
      setPlanBusy(false);
    }
  };

  const bal = usage?.credits;
  const sub = status?.subscription;
  const canManage = sub?.provider === 'stripe';
  const prepaid = sub?.provider === 'payos';
  const pastDue = sub?.status === 'past_due';
  const endingSoon = prepaid && sub.current_period_end && sub.current_period_end - Date.now() / 1000 < 3 * 86400;

  return (
    <>
      <section className="card p-5 sm:p-6 lg:col-span-2">
        <h2 className="font-display text-lg text-ink">{t('billing.account.title')}</h2>
        <p className="text-sm text-muted mt-1">{t('billing.account.sub')}</p>

        {justPaid && (
          <p role="status" className="text-sm text-ok mt-3 flex items-center gap-1.5"><Check size={14} /> {t('billing.success')}</p>
        )}
        {error && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3 py-2 mt-3">{error}</p>}
        {pastDue && <p role="alert" className="text-sm text-warn bg-warn/10 rounded-input px-3 py-2 mt-3">{t('billing.pastdue')}</p>}
        {endingSoon && (
          <p role="status" className="text-sm text-ink2 bg-paper3 rounded-input px-3 py-2 mt-3">
            {t('billing.expiring', { date: dateOf(sub.current_period_end, lang) })}
          </p>
        )}
        {sub?.cancel_at_period_end && sub.current_period_end && (
          <p role="status" className="text-sm text-ink2 bg-paper3 rounded-input px-3 py-2 mt-3">
            {t('billing.cancelled.note', { date: dateOf(sub.current_period_end, lang) })}
          </p>
        )}

        {bal ? (
          <div className="mt-5 grid sm:grid-cols-2 gap-6">
            <div>
              <p className="eyebrow">{t('billing.account.plan', { name: usage.plan_name })}</p>
              <p className="text-4xl font-display text-ink tabular-nums mt-1">
                {bal.remaining} <span className="text-base text-muted">{t('billing.account.left')}</span>
              </p>
              <ul className="text-sm text-ink2 mt-3 space-y-1">
                <li>{t('billing.account.from_plan', { n: bal.plan_remaining })}</li>
                <li>{t('billing.account.from_topup', { n: bal.topup_remaining })}</li>
                {bal.reserved > 0 && <li className="text-muted">{t('billing.account.reserved', { n: bal.reserved })}</li>}
              </ul>
              {bal.plan_expires_at && (
                <p className="text-xs text-muted mt-2">{t('billing.account.expires', { date: dateOf(bal.plan_expires_at, lang) })}</p>
              )}
              {sub?.current_period_end && (
                <p className="text-xs text-muted mt-1">
                  {t(sub.cancel_at_period_end || sub.provider === 'payos' ? 'billing.account.ends' : 'billing.account.renews',
                    { date: dateOf(sub.current_period_end, lang) })}
                </p>
              )}
            </div>
            <div className="flex flex-wrap content-start gap-2">
              <a href="#/pricing" className="btn-primary px-5 py-2.5">{t(usage.plan === 'free' ? 'billing.account.upgrade' : 'billing.account.topup')}</a>
              {usage.plan !== 'free' && <a href="#/pricing" className="btn-quiet px-5 py-2.5">{t('billing.account.upgrade')}</a>}
              {canManage && (
                <button type="button" className="btn-quiet px-5 py-2.5" onClick={openPortal} disabled={portalBusy}>
                  {portalBusy && <Loader2 size={15} className="animate-spin" />} {t('billing.account.manage')}
                </button>
              )}
              {canManage && (
                <button type="button" className="btn-quiet px-5 py-2.5" onClick={() => setRenewal(!sub.cancel_at_period_end)} disabled={planBusy}>
                  {planBusy && <Loader2 size={15} className="animate-spin" />} {t(sub.cancel_at_period_end ? 'billing.resume' : 'billing.cancel')}
                </button>
              )}
              {prepaid && (
                <button type="button" className="btn-quiet px-5 py-2.5" onClick={renewPrepaid} disabled={planBusy}>
                  {planBusy && <Loader2 size={15} className="animate-spin" />} {t('billing.renew')}
                </button>
              )}
            </div>
          </div>
        ) : <Loader2 size={18} className="animate-spin text-muted mt-5" />}
      </section>

      <section className="card p-5 sm:p-6 lg:col-span-2">
        <h2 className="font-display text-lg text-ink">{t('billing.history')}</h2>
        {!status ? <Loader2 size={18} className="animate-spin text-muted mt-4" />
          : status.payments.length === 0 ? <p className="text-sm text-muted mt-3">{t('billing.history.empty')}</p>
            : (
              <ul className="mt-4 divide-y divide-rule">
                {status.payments.map((p) => (
                  <li key={`${p.provider}:${p.provider_ref}`} className="py-3 flex items-center justify-between gap-4 text-sm">
                    <div className="min-w-0">
                      <p className="text-ink">
                        {p.kind === 'topup' ? t('billing.history.topup', { n: p.credits }) : t('billing.history.sub', { item: p.item })}
                      </p>
                      <p className="text-xs text-muted">{dateOf(p.paid_at || p.created_at, lang)} · {p.provider}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-ink tabular-nums">{amountOf(p, lang)}</p>
                      <p className={`text-xs ${p.status === 'paid' ? 'text-ok' : 'text-muted'}`}>{t(`billing.history.status.${p.status}`)}</p>
                      {p.id != null && ['paid', 'refunded'].includes(p.status) && (
                        <a href={`#/receipt/${p.id}`} className="text-xs text-brass hover:underline">{t('billing.receipt')}</a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
      </section>

      <PromoCard onRedeemed={() => { reload(); refreshMe(); }} />
      <InvoiceInfoCard />
    </>
  );
}

function PromoCard({ onRedeemed }) {
  const { t } = useLang();
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (!code.trim()) return;
    setBusy(true); setMsg(null);
    try {
      const res = await billingApi.redeem(code.trim());
      setMsg({ ok: true, text: t('billing.promo.done', { n: res.credits }) });
      setCode('');
      onRedeemed();
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(t, err) });
    } finally { setBusy(false); }
  };

  return (
    <section className="card p-5 sm:p-6">
      <h2 className="font-display text-lg text-ink">{t('billing.promo.title')}</h2>
      <p className="text-sm text-muted mt-1">{t('billing.promo.sub')}</p>
      <form onSubmit={submit} className="mt-4 flex gap-2">
        <input className="input-field flex-1 uppercase" value={code} maxLength={32} autoComplete="off"
          onChange={(e) => setCode(e.target.value)} placeholder={t('billing.promo.placeholder')} aria-label={t('billing.promo.title')} />
        <button type="submit" className="btn-quiet px-5 py-2.5" disabled={busy || !code.trim()}>
          {busy && <Loader2 size={15} className="animate-spin" />} {t('billing.promo.cta')}
        </button>
      </form>
      {msg && <p role={msg.ok ? 'status' : 'alert'} className={`text-sm mt-3 ${msg.ok ? 'text-ok' : 'text-danger'}`}>{msg.text}</p>}
    </section>
  );
}

const INFO_FIELDS = ['company', 'tax_code', 'address', 'email'];

function InvoiceInfoCard() {
  const { t } = useLang();
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    billingApi.info().then(setInfo).catch(() => setInfo({ company: '', tax_code: '', address: '', email: '' }));
  }, []);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      setInfo(await billingApi.saveInfo(info));
      setMsg({ ok: true, text: t('billing.info.saved') });
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(t, err) });
    } finally { setBusy(false); }
  };

  return (
    <section className="card p-5 sm:p-6">
      <h2 className="font-display text-lg text-ink">{t('billing.info.title')}</h2>
      <p className="text-sm text-muted mt-1">{t('billing.info.sub')}</p>
      {!info ? <Loader2 size={18} className="animate-spin text-muted mt-4" /> : (
        <form onSubmit={save} className="mt-4 space-y-3">
          {INFO_FIELDS.map((f) => (
            <label key={f} className="block">
              <span className="eyebrow">{t(`billing.info.${f}`)}</span>
              <input className="input-field mt-1.5" value={info[f] || ''} maxLength={f === 'address' ? 300 : 200}
                inputMode={f === 'tax_code' ? 'numeric' : undefined}
                onChange={(e) => setInfo({ ...info, [f]: e.target.value })} />
            </label>
          ))}
          <button type="submit" className="btn-quiet px-5 py-2.5" disabled={busy}>
            {busy && <Loader2 size={15} className="animate-spin" />} {t('billing.info.save')}
          </button>
          {msg && <p role={msg.ok ? 'status' : 'alert'} className={`text-sm ${msg.ok ? 'text-ok' : 'text-danger'}`}>{msg.text}</p>}
        </form>
      )}
    </section>
  );
}
