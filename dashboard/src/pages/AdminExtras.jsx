import { useCallback, useEffect, useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { useLang } from '../contexts/LangContext';
import { adminApi } from '../lib/studio';
import { errorMessage } from '../lib/errors';

function money(amount, currency, lang) {
  if (currency === 'vnd') {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(amount);
  }
  return new Intl.NumberFormat(lang === 'vi' ? 'vi-VN' : 'en-US', { style: 'currency', currency: (currency || 'usd').toUpperCase() }).format(amount / 100);
}

const usd = (n, lang) => new Intl.NumberFormat(lang === 'vi' ? 'vi-VN' : 'en-US', { style: 'currency', currency: 'USD' }).format(n || 0);

const day = (epoch, lang) => (epoch
  ? new Date(epoch * 1000).toLocaleDateString(lang === 'vi' ? 'vi-VN' : 'en-US', { day: 'numeric', month: 'short', year: 'numeric' })
  : '–');

function Chip({ tone = 'muted', children }) {
  const cls = { ok: 'text-ok bg-ok/10', warn: 'text-warn bg-warn/10', danger: 'text-danger bg-danger/10', muted: 'text-muted bg-paper3' }[tone];
  return <span className={`text-xs rounded-full px-2 py-0.5 ${cls}`}>{children}</span>;
}

const STATUS_TONE = { paid: 'ok', refunded: 'warn', disputed: 'danger', failed: 'danger', pending: 'muted', active: 'ok', past_due: 'danger', canceled: 'muted', expired: 'muted' };

// ---- charts and margin ---------------------------------------------------------------------
function Chart({ days }) {
  const { t } = useLang();
  const W = 640; const H = 160; const pad = 4;
  const max = Math.max(1, ...days.map((d) => Math.max(d.revenue_usd, d.cost_usd)));
  const bw = (W - pad * 2) / days.length;
  const y = (v) => H - pad - (v / max) * (H - pad * 2);
  const line = days.map((d, i) => `${pad + i * bw + bw / 2},${y(d.cost_usd)}`).join(' ');
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-40" role="img"
        aria-label={t('admin.chart.title', { n: days.length })}>
        <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} className="stroke-rule" strokeWidth="1" />
        {days.map((d, i) => (
          <rect key={d.day} x={pad + i * bw + 1} width={Math.max(1, bw - 2)} y={y(d.revenue_usd)}
            height={Math.max(0, H - pad - y(d.revenue_usd))} className="fill-brass" rx="1">
            <title>{`${d.day}: ${usd(d.revenue_usd)} / ${usd(d.cost_usd)} / +${d.signups}`}</title>
          </rect>
        ))}
        <polyline points={line} fill="none" className="stroke-ink2" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
      <figcaption className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted mt-2">
        <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-3 rounded-sm bg-brass" />{t('admin.chart.revenue')}</span>
        <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-0.5 bg-ink2" />{t('admin.chart.cost')}</span>
        <span>{t('admin.chart.signups')}: {days.reduce((n, d) => n + d.signups, 0)}</span>
      </figcaption>
    </figure>
  );
}

export function OverviewExtras({ overview }) {
  const { t, lang } = useLang();
  const [days, setDays] = useState(null);
  useEffect(() => { adminApi.series(30).then((r) => setDays(r.days)).catch(() => setDays([])); }, []);
  const eco = overview?.economics_30d;
  return (
    <div className="grid lg:grid-cols-2 gap-6 mb-10">
      <section className="card p-5">
        <h2 className="font-display text-lg text-ink mb-3">{t('admin.chart.title', { n: 30 })}</h2>
        {days === null ? <Loader2 size={18} className="animate-spin text-muted" /> : <Chart days={days} />}
      </section>
      {eco && (
        <section className="card p-5">
          <h2 className="font-display text-lg text-ink mb-3">{t('admin.econ.title')}</h2>
          <dl className="grid grid-cols-3 gap-3 text-sm">
            <div><dt className="eyebrow">{t('admin.econ.revenue')}</dt><dd className="text-xl font-display tabular-nums mt-1">{usd(eco.revenue_usd, lang)}</dd></div>
            <div><dt className="eyebrow">{t('admin.econ.ai')}</dt><dd className="text-xl font-display tabular-nums mt-1">{usd(eco.ai_cost_usd, lang)}</dd></div>
            <div><dt className="eyebrow">{t('admin.econ.margin')}</dt>
              <dd className={`text-xl font-display tabular-nums mt-1 ${eco.margin_usd < 0 ? 'text-danger' : 'text-ok'}`}>{usd(eco.margin_usd, lang)}</dd></div>
          </dl>
          {Object.keys(eco.by_plan).length > 0 && (
            <table className="w-full text-xs mt-4">
              <thead><tr className="text-left text-muted"><th className="font-normal py-1">{t('admin.econ.byplan')}</th>
                <th className="font-normal text-right">{t('admin.econ.revenue')}</th><th className="font-normal text-right">{t('admin.econ.ai')}</th>
                <th className="font-normal text-right">{t('admin.econ.margin')}</th></tr></thead>
              <tbody className="divide-y divide-rule">
                {Object.entries(eco.by_plan).map(([plan, r]) => (
                  <tr key={plan}><td className="py-1.5 text-ink2">{plan}</td>
                    <td className="text-right tabular-nums">{usd(r.revenue_usd, lang)}</td>
                    <td className="text-right tabular-nums">{usd(r.cost_usd, lang)}</td>
                    <td className="text-right tabular-nums">{usd(r.margin_usd, lang)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="text-xs text-muted mt-3">{t('admin.econ.note', { rate: eco.vnd_per_usd.toLocaleString(lang === 'vi' ? 'vi-VN' : 'en-US') })}</p>
        </section>
      )}
    </div>
  );
}

// A CSV is fetched with the bearer token, then saved from a blob.
export function ExportButtons() {
  const { t } = useLang();
  const [busy, setBusy] = useState('');
  const save = async (kind) => {
    setBusy(kind);
    try {
      const blob = await adminApi.exportCsv(kind);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `${kind}.csv`; a.click();
      URL.revokeObjectURL(url);
    } finally { setBusy(''); }
  };
  return (
    <div className="flex flex-wrap gap-2">
      {['users', 'payments'].map((k) => (
        <button key={k} type="button" className="btn-quiet px-3 py-2 text-sm" onClick={() => save(k)} disabled={!!busy}>
          {busy === k ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />} {t(`admin.export.${k}`)}
        </button>
      ))}
    </div>
  );
}

// ---- payments tab ----------------------------------------------------------------------------
const PAGE = 50;

function Table({ head, children, empty }) {
  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm min-w-[40rem]">
        <thead><tr className="text-left text-muted text-xs">{head.map((h) => <th key={h} className="px-4 py-3 font-normal">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-rule">{children}</tbody>
      </table>
      {empty}
    </div>
  );
}

export function PaymentsTab({ onOpenUser }) {
  const { t, lang } = useLang();
  const [status, setStatus] = useState('');
  const [provider, setProvider] = useState('');
  const [q, setQ] = useState('');
  const [list, setList] = useState({ total: 0, payments: [] });
  const [subs, setSubs] = useState({ total: 0, subscriptions: [] });
  const [invoices, setInvoices] = useState([]);

  useEffect(() => {
    const h = setTimeout(() => adminApi.payments({ status, provider, q, limit: PAGE }).then(setList).catch(() => {}), 250);
    return () => clearTimeout(h);
  }, [status, provider, q]);
  useEffect(() => {
    adminApi.subscriptions({ limit: PAGE }).then(setSubs).catch(() => {});
    adminApi.invoiceRequests().then((r) => setInvoices(r.requests)).catch(() => {});
  }, []);

  const more = async () => {
    const next = await adminApi.payments({ status, provider, q, limit: PAGE, offset: list.payments.length });
    setList((cur) => ({ ...next, payments: [...cur.payments, ...next.payments] }));
  };

  const select = 'input-field w-auto py-2 text-sm';
  return (
    <div className="space-y-12">
      <section>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 className="font-display text-xl text-ink">{t('admin.payments.title')} <span className="text-muted text-base">({list.total})</span></h2>
          <div className="flex flex-wrap gap-2">
            <select className={select} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="status">
              <option value="">{t('admin.filter.all')}</option>
              {['paid', 'pending', 'refunded', 'disputed', 'failed'].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <select className={select} value={provider} onChange={(e) => setProvider(e.target.value)} aria-label="provider">
              <option value="">{t('admin.filter.all')}</option>
              <option value="stripe">Stripe</option><option value="payos">PayOS</option>
            </select>
            <input className={`${select} w-56`} value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('admin.filter.search')} />
          </div>
        </div>
        <Table head={[t('admin.col.user'), t('admin.col.item'), t('admin.col.amount'), t('admin.col.provider'), t('admin.col.status'), t('admin.col.date')]}
          empty={list.payments.length === 0 && <p className="px-4 py-6 text-center text-muted text-sm">{t('admin.system.empty')}</p>}>
          {list.payments.map((p) => (
            <tr key={p.id} className="hover:bg-paper3/50 cursor-pointer" onClick={() => onOpenUser(p.user_id)}>
              <td className="px-4 py-3 text-ink">{p.email}</td>
              <td className="px-4 py-3 text-ink2">{p.kind === 'topup' ? `${p.credits} credit` : p.item}</td>
              <td className="px-4 py-3 tabular-nums">{money(p.amount, p.currency, lang)}</td>
              <td className="px-4 py-3 text-ink2">{p.provider}</td>
              <td className="px-4 py-3"><Chip tone={STATUS_TONE[p.status]}>{p.status}</Chip></td>
              <td className="px-4 py-3 text-muted">{day(p.paid_at || p.created_at, lang)}</td>
            </tr>
          ))}
        </Table>
        {list.payments.length < list.total && (
          <button type="button" className="btn-quiet px-5 py-2.5 mt-4" onClick={more}>{t('admin.more')}</button>
        )}
      </section>

      <section>
        <h2 className="font-display text-xl text-ink mb-4">{t('admin.invoice.title')} <span className="text-muted text-base">({invoices.length})</span></h2>
        {invoices.length === 0 ? <p className="text-sm text-muted">{t('admin.invoice.empty')}</p> : (
          <ul className="card divide-y divide-rule text-sm">
            {invoices.map((r) => (
              <li key={r.id} className="px-4 py-3 flex flex-wrap justify-between gap-x-6 gap-y-1">
                <span className="text-ink">{r.company || '–'} <span className="text-muted">· MST {r.tax_code || '–'}</span><br />
                  <span className="text-xs text-muted">{r.address || '–'} · {r.invoice_email || r.email}</span></span>
                <span className="text-right text-ink2 tabular-nums">{money(r.amount, r.currency, lang)}
                  <br /><span className="text-xs text-muted">{r.provider}:{r.provider_ref} · {day(r.paid_at, lang)}</span></span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="font-display text-xl text-ink mb-4">{t('admin.subs.title')} <span className="text-muted text-base">({subs.total})</span></h2>
        <Table head={[t('admin.col.user'), t('admin.col.plan'), t('admin.col.provider'), t('admin.col.status'), t('admin.col.ends')]}
          empty={subs.subscriptions.length === 0 && <p className="px-4 py-6 text-center text-muted text-sm">{t('admin.system.empty')}</p>}>
          {subs.subscriptions.map((s) => (
            <tr key={s.id} className="hover:bg-paper3/50 cursor-pointer" onClick={() => onOpenUser(s.user_id)}>
              <td className="px-4 py-3 text-ink">{s.email}</td>
              <td className="px-4 py-3 text-ink2">{s.plan}</td>
              <td className="px-4 py-3 text-ink2">{s.provider}</td>
              <td className="px-4 py-3"><Chip tone={STATUS_TONE[s.status]}>{s.status}</Chip> {s.cancel_at_period_end && <Chip tone="warn">{t('admin.sub.cancelling')}</Chip>}</td>
              <td className="px-4 py-3 text-muted">{day(s.current_period_end, lang)}</td>
            </tr>
          ))}
        </Table>
      </section>
    </div>
  );
}

// ---- system tab: failed projects, webhook log, audit trail -------------------------------------
const AUDIT_ACTIONS = ['grant', 'refund', 'disable', 'enable', 'set_plan', 'verify_email', 'send_reset', 'delete_user', 'export',
  'promo_create', 'promo_on', 'promo_off'];

export function SystemTab() {
  const { t, lang } = useLang();
  const [failed, setFailed] = useState(null);
  const [events, setEvents] = useState(null);
  const [action, setAction] = useState('');
  const [offset, setOffset] = useState(0);
  const [audit, setAudit] = useState(null);

  useEffect(() => {
    adminApi.failedProjects().then((r) => setFailed(r.projects)).catch(() => setFailed([]));
    adminApi.webhookEvents().then((r) => setEvents(r.events)).catch(() => setEvents([]));
  }, []);
  useEffect(() => {
    adminApi.audit({ limit: PAGE, offset, action }).then((r) => setAudit(r.entries)).catch(() => setAudit([]));
  }, [action, offset]);

  const actionText = (e) => t(`admin.action.${e.action}`, e.detail || {});
  const list = (items, render) => (items === null ? <Loader2 size={18} className="animate-spin text-muted" />
    : items.length === 0 ? <p className="text-sm text-muted">{t('admin.system.empty')}</p>
      : <ul className="card divide-y divide-rule text-sm">{items.map(render)}</ul>);

  return (
    <div className="space-y-12">
      <section>
        <h2 className="font-display text-xl text-ink mb-3">{t('admin.system.failed')}</h2>
        {list(failed, (p) => (
          <li key={p.job_id} className="px-4 py-2.5 flex flex-wrap justify-between gap-x-4">
            <span className="text-ink2">{p.title || p.job_id} <span className="text-muted">· {p.email}</span></span>
            <span className="text-xs text-muted">{p.job_id} · {day(p.updated_at, lang)}</span>
          </li>
        ))}
      </section>
      <section>
        <h2 className="font-display text-xl text-ink mb-3">{t('admin.system.events')}</h2>
        {list(events, (e) => (
          <li key={e.id} className="px-4 py-2.5 flex flex-wrap justify-between gap-x-4">
            <span className="text-ink2">{e.provider} · {e.type}</span>
            <span className="text-xs text-muted break-all">{e.event_id} · {day(e.created_at, lang)}</span>
          </li>
        ))}
      </section>
      <section>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h2 className="font-display text-xl text-ink">{t('admin.audit')}</h2>
          <select className="input-field w-auto py-2 text-sm" value={action} aria-label={t('admin.audit.filter')}
            onChange={(e) => { setOffset(0); setAction(e.target.value); }}>
            <option value="">{t('admin.filter.all')}</option>
            {AUDIT_ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        {list(audit, (e) => (
          <li key={e.id} className="px-4 py-2.5 flex flex-wrap justify-between gap-x-4">
            <span className="text-ink2">{actionText(e)} <span className="text-muted">· {e.user_email || e.user_id || ''}</span></span>
            <span className="text-xs text-muted">{e.admin_email} · {day(e.created_at, lang)}</span>
          </li>
        ))}
        <div className="flex gap-2 mt-3">
          <button type="button" className="btn-quiet px-4 py-2 text-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>{t('admin.audit.prev')}</button>
          <button type="button" className="btn-quiet px-4 py-2 text-sm" disabled={!audit || audit.length < PAGE} onClick={() => setOffset(offset + PAGE)}>{t('admin.audit.next')}</button>
        </div>
      </section>
    </div>
  );
}

// ---- promo codes ------------------------------------------------------------------------------
export function PromosTab() {
  const { t, lang } = useLang();
  const [codes, setCodes] = useState(null);
  const [form, setForm] = useState({ code: '', credits: '', max_uses: '0', expires: '', note: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => adminApi.promos().then((r) => setCodes(r.codes)).catch(() => setCodes([])), []);
  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      await adminApi.createPromo({
        code: form.code.trim(), credits: parseInt(form.credits, 10) || 0, max_uses: parseInt(form.max_uses, 10) || 0,
        expires_at: form.expires ? new Date(`${form.expires}T23:59:59`).getTime() / 1000 : null, note: form.note.trim(),
      });
      setForm({ code: '', credits: '', max_uses: '0', expires: '', note: '' });
      await load();
    } catch (err) {
      setError(errorMessage(t, err, { code_exists: 'admin.err.code_exists', bad_code: 'admin.err.bad_code', bad_amount: 'admin.err.bad_amount' }));
    } finally { setBusy(false); }
  };

  const toggle = async (c) => { await adminApi.setPromoActive(c.code, !c.active); load(); };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="space-y-8">
      <form onSubmit={create} className="card p-5 grid sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
        <label className="block"><span className="eyebrow">{t('admin.promos.code')}</span>
          <input className="input-field mt-1.5 uppercase" value={form.code} maxLength={32} onChange={set('code')} required /></label>
        <label className="block"><span className="eyebrow">{t('admin.promos.credits')}</span>
          <input className="input-field mt-1.5" inputMode="numeric" value={form.credits} onChange={(e) => setForm({ ...form, credits: e.target.value.replace(/\D/g, '') })} required /></label>
        <label className="block"><span className="eyebrow">{t('admin.promos.max')}</span>
          <input className="input-field mt-1.5" inputMode="numeric" value={form.max_uses} onChange={(e) => setForm({ ...form, max_uses: e.target.value.replace(/\D/g, '') })} /></label>
        <label className="block"><span className="eyebrow">{t('admin.promos.expires')}</span>
          <input type="date" className="input-field mt-1.5" value={form.expires} onChange={set('expires')} /></label>
        <label className="block"><span className="eyebrow">{t('admin.promos.note')}</span>
          <input className="input-field mt-1.5" maxLength={200} value={form.note} onChange={set('note')} /></label>
        <div className="sm:col-span-2 lg:col-span-5 flex items-center gap-3">
          <button type="submit" className="btn-primary px-5 py-2.5" disabled={busy || !form.code || !form.credits}>
            {busy && <Loader2 size={15} className="animate-spin" />} {t('admin.promos.create')}
          </button>
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        </div>
      </form>

      <section>
        <h2 className="font-display text-xl text-ink mb-3">{t('admin.promos.title')}</h2>
        {codes === null ? <Loader2 size={18} className="animate-spin text-muted" />
          : codes.length === 0 ? <p className="text-sm text-muted">{t('admin.promos.empty')}</p> : (
            <ul className="card divide-y divide-rule text-sm">
              {codes.map((c) => (
                <li key={c.code} className="px-4 py-3 flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-ink font-mono">{c.code} <span className="font-sans text-ink2">· {c.credits} credit</span></p>
                    <p className="text-xs text-muted">
                      {t('admin.promos.used')} {c.used}{c.max_uses ? `/${c.max_uses}` : ''}
                      {c.expires_at ? ` · ${t('admin.promos.expires')} ${day(c.expires_at, lang)}` : ''}{c.note ? ` · ${c.note}` : ''}
                    </p>
                  </div>
                  <button type="button" className="btn-quiet px-3 py-1.5 text-xs" onClick={() => toggle(c)}>
                    {t(c.active ? 'admin.promos.off' : 'admin.promos.on')}
                  </button>
                </li>
              ))}
            </ul>
          )}
      </section>
    </div>
  );
}
