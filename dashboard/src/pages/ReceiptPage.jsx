import { useEffect, useState } from 'react';
import { Loader2, Printer, ArrowLeft } from 'lucide-react';
import { useLang } from '../contexts/LangContext';
import { billingApi } from '../lib/studio';
import { errorMessage } from '../lib/errors';

function amountOf(p, lang) {
  if (p.currency?.toLowerCase() === 'vnd') {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(p.amount);
  }
  return new Intl.NumberFormat(lang === 'vi' ? 'vi-VN' : 'en-US', { style: 'currency', currency: (p.currency || 'usd').toUpperCase() })
    .format(p.amount / 100);
}

function Party({ title, lines }) {
  const { t } = useLang();
  return (
    <div>
      <p className="eyebrow">{title}</p>
      <div className="mt-1.5 text-sm text-ink space-y-0.5">
        {lines.map(([k, label, v]) => (
          <p key={k}><span className="text-muted">{label}: </span>{v || <span className="text-muted">{t('receipt.unset')}</span>}</p>
        ))}
      </div>
    </div>
  );
}

// A printable receipt for one settled payment. Not a VAT invoice: the note says so and
// points to the invoice request, which the operator answers by hand.
export default function ReceiptPage({ paymentId }) {
  const { t, lang } = useLang();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    billingApi.receipt(paymentId).then(setData)
      .catch((e) => setError(e.status === 404 ? t('receipt.notfound') : errorMessage(t, e)));
  }, [paymentId, t]);

  const requestInvoice = async () => {
    setBusy(true); setMsg(null);
    try {
      await billingApi.requestInvoice(paymentId);
      setData((d) => ({ ...d, payment: { ...d.payment, invoice_requested_at: Date.now() / 1000 } }));
    } catch (e) {
      setMsg(errorMessage(t, e));
    } finally { setBusy(false); }
  };

  const p = data?.payment;
  const date = p && new Date((p.paid_at || p.created_at) * 1000)
    .toLocaleDateString(lang === 'vi' ? 'vi-VN' : 'en-US', { day: 'numeric', month: 'long', year: 'numeric' });

  return (
    <div className="min-h-screen bg-paper print:bg-white">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
        <div className="flex items-center justify-between gap-3 mb-6 print:hidden">
          <a href="#/account" className="btn-quiet px-4 py-2"><ArrowLeft size={15} /> {t('receipt.back')}</a>
          {p && <button type="button" className="btn-primary px-4 py-2" onClick={() => window.print()}><Printer size={15} /> {t('receipt.print')}</button>}
        </div>

        {error && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3 py-2">{error}</p>}
        {!data && !error && <Loader2 size={20} className="animate-spin text-muted" />}

        {p && (
          <article className="card p-6 sm:p-8 print:shadow-none print:border-0">
            <h1 className="font-display text-2xl text-ink">{t('receipt.title')}</h1>
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
              <dt className="text-muted">{t('receipt.no')}</dt><dd className="text-ink tabular-nums text-right break-all">{p.provider}:{p.provider_ref}</dd>
              <dt className="text-muted">{t('receipt.date')}</dt><dd className="text-ink text-right">{date}</dd>
            </dl>

            <div className="grid sm:grid-cols-2 gap-6 mt-8">
              <Party title={t('receipt.seller')} lines={[
                ['name', t('receipt.name'), data.seller.name], ['tax', t('billing.info.tax_code'), data.seller.tax_code],
                ['address', t('billing.info.address'), data.seller.address], ['email', 'Email', data.seller.email]]} />
              <Party title={t('receipt.buyer')} lines={[
                ['name', t('receipt.name'), data.buyer.company || data.buyer.name], ['tax', t('billing.info.tax_code'), data.buyer.tax_code],
                ['address', t('billing.info.address'), data.buyer.address], ['email', 'Email', data.buyer.email || data.buyer.account_email]]} />
            </div>

            <div className="mt-8 border-t border-rule pt-4 flex items-start justify-between gap-4 text-sm">
              <div>
                <p className="eyebrow">{t('receipt.item')}</p>
                <p className="text-ink mt-1.5">
                  {p.kind === 'topup' ? t('receipt.topup', { n: p.credits }) : t('receipt.sub', { item: p.item })}
                </p>
                {p.status !== 'paid' && <p className="text-xs text-muted mt-1">{t(`billing.history.status.${p.status}`)}</p>}
              </div>
              <div className="text-right">
                <p className="eyebrow">{t('receipt.total')}</p>
                <p className="text-xl font-display text-ink tabular-nums mt-1">{amountOf(p, lang)}</p>
              </div>
            </div>

            <p className="text-xs text-muted mt-8">{t('receipt.note')}</p>

            {p.status === 'paid' && (
              <div className="mt-4 print:hidden">
                {p.invoice_requested_at
                  ? <p className="text-sm text-ok">{t('billing.invoice.requested')}</p>
                  : <button type="button" className="btn-quiet px-4 py-2" onClick={requestInvoice} disabled={busy}>
                    {busy && <Loader2 size={15} className="animate-spin" />} {t('billing.invoice.request')}
                  </button>}
                {msg && <p role="alert" className="text-sm text-danger mt-2">{msg}</p>}
              </div>
            )}
          </article>
        )}
      </div>
    </div>
  );
}
