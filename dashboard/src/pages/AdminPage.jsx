import { useCallback, useEffect, useState } from 'react';
import { Loader2, Search } from 'lucide-react';
import StudioShell from '../StudioShell';
import Modal from '../components/ui/Modal';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';
import { adminApi } from '../lib/studio';
import { errorMessage } from '../lib/errors';
import { OverviewExtras, ExportButtons, PaymentsTab, SystemTab, PromosTab } from './AdminExtras';

const PAGE = 50;
const TABS = ['overview', 'users', 'payments', 'system', 'promos'];

function money(amount, currency, lang) {
  if (currency === 'vnd') {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(amount);
  }
  return new Intl.NumberFormat(lang === 'vi' ? 'vi-VN' : 'en-US', { style: 'currency', currency: (currency || 'usd').toUpperCase() }).format(amount / 100);
}

const day = (epoch, lang) => (epoch
  ? new Date(epoch * 1000).toLocaleDateString(lang === 'vi' ? 'vi-VN' : 'en-US', { day: 'numeric', month: 'short', year: 'numeric' })
  : '–');

function Stat({ label, children, sub }) {
  return (
    <div className="card p-4 sm:p-5">
      <p className="eyebrow">{label}</p>
      <div className="text-2xl font-display text-ink tabular-nums mt-1.5">{children}</div>
      {sub && <p className="text-xs text-muted mt-1.5 space-y-0.5">{sub}</p>}
    </div>
  );
}

function Chip({ tone = 'muted', children }) {
  const cls = { ok: 'text-ok bg-ok/10', warn: 'text-warn bg-warn/10', danger: 'text-danger bg-danger/10', muted: 'text-muted bg-paper3' }[tone];
  return <span className={`text-xs rounded-full px-2 py-0.5 ${cls}`}>{children}</span>;
}

function UserDetail({ id, onClose, onChanged }) {
  const { t, lang } = useLang();
  const { user: me } = useAuth();
  const [d, setD] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState('pro');
  const [days, setDays] = useState('30');
  const [refunding, setRefunding] = useState(null);   // the payment whose refund note is being typed
  const [refundNote, setRefundNote] = useState('');

  const load = useCallback(() => adminApi.user(id).then(setD).catch((e) => setError(e.message)), [id]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn, done) => {
    setBusy(true); setError(''); setNotice('');
    try {
      const res = await fn();
      if (done) setNotice(done(res));
      await load();
      onChanged();
    } catch (e) {
      setError(t('admin.err', { error: errorMessage(t, e, {
        admin_account: 'admin.err.admin_account', cancel_failed: 'admin.err.cancel_failed' }) }));
    } finally { setBusy(false); }
  };

  const refund = (p) => {
    act(() => adminApi.refund(p.id, refundNote.trim()), (r) => {
      setRefunding(null); setRefundNote('');
      return [t('admin.refund.done', { n: r.clawed_back }),
        r.unrecovered ? t('admin.refund.unrecovered', { n: r.unrecovered }) : '',
        r.provider_cancel_failed?.length ? t('admin.refund.cancelfail', { ids: r.provider_cancel_failed.join(', ') }) : '']
        .filter(Boolean).join(' ');
    });
  };
  const applyPlan = () => act(() => adminApi.setPlan(d.id, plan, parseInt(days, 10) || 30, ''));
  const verify = () => act(() => adminApi.verifyEmail(d.id), () => t('admin.user.verified'));
  const resetMail = () => act(() => adminApi.sendReset(d.id), () => t('admin.user.sent'));
  const remove = async () => {
    if (!window.confirm(t('admin.user.delete.confirm', { email: d.email }))) return;
    setBusy(true); setError('');
    try {
      await adminApi.deleteUser(d.id);
      onChanged();
      onClose();
    } catch (e) {
      setError(t('admin.err', { error: errorMessage(t, e, { admin_account: 'admin.err.admin_account', cancel_failed: 'admin.err.cancel_failed' }) }));
      setBusy(false);
    }
  };
  const toggle = () => {
    if (!d.disabled && !window.confirm(t('admin.disable.confirm'))) return;
    act(() => (d.disabled ? adminApi.enable(d.id) : adminApi.disable(d.id)));
  };
  const grant = (e) => {
    e.preventDefault();
    const n = parseInt(amount, 10);
    if (!n || n < 1) return;
    act(() => adminApi.grant(d.id, n, note.trim()), () => { setAmount(''); setNote(''); return t('admin.grant.done'); });
  };

  return (
    <Modal isOpen onClose={onClose} size="lg" title={d?.email || '…'}>
      {!d ? (error ? <p role="alert" className="text-sm text-danger">{error}</p> : <Loader2 size={18} className="animate-spin text-muted" />) : (
        <div className="space-y-6">
          {error && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3 py-2">{error}</p>}
          {notice && <p role="status" className="text-sm text-ok">{notice}</p>}

          <div className="flex flex-wrap items-center gap-2 text-sm text-ink2">
            <Chip>{d.plan}</Chip>
            <Chip tone={d.verified ? 'ok' : 'warn'}>{t(d.verified ? 'admin.status.verified' : 'admin.status.unverified')}</Chip>
            {d.disabled && <Chip tone="danger">{t('admin.status.disabled')}</Chip>}
            <span className="text-muted">{t('admin.detail.projects', { n: d.projects })}</span>
            <span className="text-muted">· {day(d.created_at, lang)}</span>
          </div>
          <p className="text-sm text-ink2">{t('admin.detail.credits', { plan: d.credits.plan_remaining, topup: d.credits.topup_remaining })}</p>
          <p className="text-xs text-muted">
            {t('admin.user.revenue')}: ${d.revenue_usd} · {t('admin.user.cost')}: ${d.ai_cost_usd}
            {d.subscriptions?.[0] && ` · ${d.subscriptions[0].provider} ${d.subscriptions[0].plan} (${d.subscriptions[0].status})`}
          </p>

          <div className="flex flex-wrap items-end gap-2">
            <label className="block"><span className="eyebrow">{t('admin.user.setplan')}</span>
              <select className="input-field mt-1.5 w-auto" value={plan} onChange={(e) => setPlan(e.target.value)}>
                {['free', 'starter', 'pro'].map((p) => <option key={p} value={p}>{p}</option>)}
              </select></label>
            <label className="block"><span className="eyebrow">{t('admin.user.days')}</span>
              <input className="input-field mt-1.5 w-20" inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value.replace(/\D/g, ''))} /></label>
            <button type="button" className="btn-quiet px-4 py-2.5" onClick={applyPlan} disabled={busy}>{t('admin.user.apply')}</button>
            {!d.verified && <button type="button" className="btn-quiet px-4 py-2.5" onClick={verify} disabled={busy}>{t('admin.user.verify')}</button>}
            <button type="button" className="btn-quiet px-4 py-2.5" onClick={resetMail} disabled={busy}>{t('admin.user.reset')}</button>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <form onSubmit={grant} className="flex flex-wrap items-end gap-2">
              <label className="block">
                <span className="eyebrow">{t('admin.grant.amount')}</span>
                <input className="input-field mt-1.5 w-28" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value.replace(/\D/g, ''))} />
              </label>
              <label className="block">
                <span className="eyebrow">{t('admin.grant.note')}</span>
                <input className="input-field mt-1.5 w-56" maxLength={200} value={note} onChange={(e) => setNote(e.target.value)} />
              </label>
              <button type="submit" className="btn-quiet px-4 py-2.5" disabled={busy || !amount}>{t('admin.grant.cta')}</button>
            </form>
            {d.id !== me?.id && (
              <button type="button" className={`${d.disabled ? 'btn-quiet' : 'btn-danger'} px-4 py-2.5 ml-auto`} onClick={toggle} disabled={busy}>
                {t(d.disabled ? 'admin.enable' : 'admin.disable')}
              </button>
            )}
          </div>

          <section>
            <h3 className="font-display text-lg text-ink">{t('admin.detail.payments')}</h3>
            {d.payments.length === 0 ? <p className="text-sm text-muted mt-2">{t('admin.detail.nopayments')}</p> : (
              <ul className="mt-2 divide-y divide-rule">
                {d.payments.map((p) => (
                  <li key={p.id} className="py-2.5 flex flex-wrap items-center justify-between gap-3 text-sm">
                    <div className="min-w-0">
                      <p className="text-ink">{p.kind === 'topup' ? `${p.credits} credit` : p.item} · {money(p.amount, p.currency, lang)}</p>
                      <p className="text-xs text-muted">{day(p.paid_at || p.created_at, lang)} · {p.provider} · {p.status}</p>
                    </div>
                    {p.status === 'paid' && refunding !== p.id && (
                      <button type="button" className="btn-quiet px-3 py-1.5 text-xs shrink-0" disabled={busy}
                        onClick={() => { setRefunding(p.id); setRefundNote(''); }}>{t('admin.refund')}</button>
                    )}
                    {refunding === p.id && (
                      <div className="w-full basis-full space-y-2">
                        <p className="text-xs text-muted">{t('admin.refund.confirm')}</p>
                        <input className="input-field" maxLength={200} value={refundNote} onChange={(e) => setRefundNote(e.target.value)}
                          placeholder={t('admin.refund.note')} aria-label={t('admin.refund.note')} />
                        <div className="flex gap-2">
                          <button type="button" className="btn-danger px-3 py-1.5 text-xs" disabled={busy} onClick={() => refund(p)}>{t('admin.refund')}</button>
                          <button type="button" className="btn-quiet px-3 py-1.5 text-xs" onClick={() => setRefunding(null)}>{t('common.cancel')}</button>
                        </div>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {d.id !== me?.id && (
            <div className="pt-2 border-t border-rule">
              <button type="button" className="btn-danger px-4 py-2.5" onClick={remove} disabled={busy}>{t('admin.user.delete')}</button>
            </div>
          )}

          {d.ledger.length > 0 && (
            <section>
              <h3 className="font-display text-lg text-ink">{t('admin.detail.ledger')}</h3>
              <ul className="mt-2 text-xs text-muted space-y-1">
                {d.ledger.map((l) => (
                  <li key={`${l.kind}:${l.ref}`} className="flex justify-between gap-3">
                    <span className="truncate">{l.kind} · {l.ref}</span>
                    <span className="tabular-nums shrink-0">{l.credits} · {l.status}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </Modal>
  );
}

export default function AdminPage() {
  const { t, lang } = useLang();
  const { user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [list, setList] = useState({ total: 0, users: [] });
  const [q, setQ] = useState('');
  const [error, setError] = useState('');
  const [loadingMore, setLoadingMore] = useState(false);
  const [open, setOpen] = useState(null);
  const [tab, setTab] = useState(() => {
    try { const saved = sessionStorage.getItem('vs_admin_tab'); return TABS.includes(saved) ? saved : 'overview'; } catch (_) { return 'overview'; }
  });
  const pick = (id) => { setTab(id); try { sessionStorage.setItem('vs_admin_tab', id); } catch (_) { /* private mode */ } };

  const loadOverview = useCallback(() => adminApi.overview().then(setOverview).catch((e) => setError(e.message)), []);
  const loadUsers = useCallback((query) => adminApi.users({ q: query, limit: PAGE }).then(setList).catch((e) => setError(e.message)), []);

  useEffect(() => { loadOverview(); }, [loadOverview]);
  useEffect(() => {
    const h = setTimeout(() => loadUsers(q), 250);   // typing, not one request per key
    return () => clearTimeout(h);
  }, [q, loadUsers]);

  const more = async () => {
    setLoadingMore(true);
    try {
      const next = await adminApi.users({ q, limit: PAGE, offset: list.users.length });
      setList((cur) => ({ ...next, users: [...cur.users, ...next.users] }));
    } catch (e) { setError(e.message); }
    finally { setLoadingMore(false); }
  };

  // The server answers 404 to non-admins. Say so instead of leaving a blank screen.
  if (!user?.is_admin) {
    return (
      <StudioShell active="admin">
        <div className="max-w-md mx-auto text-center py-20">
          <h1 className="font-display text-2xl text-ink">{t('admin.denied.title')}</h1>
          <p className="mt-3 text-muted">{t('admin.denied.body')}</p>
          <a href="#/projects" className="btn-primary mt-6 inline-flex">{t('admin.denied.back')}</a>
        </div>
      </StudioShell>
    );
  }

  const currencies = overview ? Object.keys(overview.revenue) : [];

  return (
    <StudioShell active="admin" wide>
      <h1 className="font-display text-3xl text-ink mb-6">{t('admin.title')}</h1>
      {error && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3 py-2 mb-6">{t('admin.err', { error })}</p>}

      <div role="tablist" className="flex flex-wrap gap-1 border-b border-rule mb-8">
        {TABS.map((id) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => pick(id)}
            className={`px-4 py-2.5 text-sm -mb-px border-b-2 transition-colors ${tab === id ? 'border-brass text-ink' : 'border-transparent text-muted hover:text-ink2'}`}>
            {t(`admin.tab.${id}`)}
          </button>
        ))}
      </div>

      {tab === 'overview' && overview && (
        <section className="mb-10">
          {!overview.mail_enabled && <p className="text-sm text-warn bg-warn/10 rounded-input px-3 py-2 mb-4">{t('admin.mail.off')}</p>}
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <Stat label={t('admin.users.total')}
              sub={<><span className="block">{t('admin.users.new', { n: overview.users.last_7d })}</span><span className="block">{t('admin.users.verified', { n: overview.users.verified })}</span></>}>
              {overview.users.total}
            </Stat>
            <Stat label={t('admin.paying')}
              sub={Object.entries(overview.users.by_plan).map(([p, n]) => `${p} ${n}`).join(' · ')}>
              {overview.paying}
            </Stat>
            <Stat label={t('admin.revenue')}
              sub={currencies.map((c) => (
                <span key={c} className="block">
                  {t('admin.revenue.last30', { amount: money(overview.revenue[c].last_30d, c, lang) })}
                  {overview.revenue[c].refunded > 0 && ` · ${t('admin.revenue.refunded', { amount: money(overview.revenue[c].refunded, c, lang) })}`}
                </span>
              ))}>
              {currencies.length === 0 ? '–' : currencies.map((c) => <div key={c}>{money(overview.revenue[c].total, c, lang)}</div>)}
            </Stat>
            <Stat label={`${t('admin.spent')} · ${t('admin.spent.today')}`}
              sub={overview.daily_budget ? t('admin.spent.budget', { n: overview.daily_budget }) : t('admin.spent.nobudget')}>
              {overview.credits_spent_today}
            </Stat>
          </div>
          {Object.keys(overview.credits_spent_30d).length > 0 && (
            <p className="text-xs text-muted mt-3">
              {t('admin.spent.30d')}: {Object.entries(overview.credits_spent_30d).map(([k, v]) => `${k} ${v}`).join(' · ')}
            </p>
          )}
          <div className="mt-8"><OverviewExtras overview={overview} /></div>
          <ExportButtons />
        </section>
      )}

      {tab === 'users' && (
      <section>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 className="font-display text-xl text-ink">{t('admin.users')} <span className="text-muted text-base">({list.total})</span></h2>
          <label className="relative block w-full sm:w-72">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input className="input-field pl-9" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('admin.search')} />
          </label>
        </div>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm min-w-[40rem]">
            <thead>
              <tr className="text-left text-muted text-xs">
                <th className="px-4 py-3 font-normal">{t('admin.col.email')}</th>
                <th className="px-4 py-3 font-normal">{t('admin.col.plan')}</th>
                <th className="px-4 py-3 font-normal text-right">{t('admin.col.credits')}</th>
                <th className="px-4 py-3 font-normal">{t('admin.col.status')}</th>
                <th className="px-4 py-3 font-normal">{t('admin.col.joined')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {list.users.map((u) => (
                <tr key={u.id} className="hover:bg-paper3/50 cursor-pointer" onClick={() => setOpen(u.id)}>
                  <td className="px-4 py-3 text-ink">
                    <button type="button" className="text-left" onClick={(e) => { e.stopPropagation(); setOpen(u.id); }}>{u.email}</button>
                  </td>
                  <td className="px-4 py-3 text-ink2">{u.plan}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{u.credits_left}</td>
                  <td className="px-4 py-3 space-x-1">
                    <Chip tone={u.verified ? 'ok' : 'warn'}>{t(u.verified ? 'admin.status.verified' : 'admin.status.unverified')}</Chip>
                    {u.disabled && <Chip tone="danger">{t('admin.status.disabled')}</Chip>}
                  </td>
                  <td className="px-4 py-3 text-muted">{day(u.created_at, lang)}</td>
                </tr>
              ))}
              {list.users.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-6 text-center text-muted">{t('admin.none')}</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {list.users.length < list.total && (
          <button type="button" className="btn-quiet px-5 py-2.5 mt-4" onClick={more} disabled={loadingMore}>
            {loadingMore && <Loader2 size={15} className="animate-spin" />} {t('admin.more')}
          </button>
        )}
      </section>

      )}

      {tab === 'payments' && <PaymentsTab onOpenUser={setOpen} />}
      {tab === 'system' && <SystemTab />}
      {tab === 'promos' && <PromosTab />}

      {open != null && <UserDetail id={open} onClose={() => setOpen(null)} onChanged={() => { loadOverview(); loadUsers(q); }} />}
    </StudioShell>
  );
}
