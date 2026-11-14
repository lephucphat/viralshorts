import { useCallback, useEffect, useState } from 'react';
import { Check, Copy, KeyRound, Loader2, Trash2, AlertTriangle } from 'lucide-react';
import Modal from './ui/Modal';
import { useLang } from '../contexts/LangContext';
import { keysApi } from '../lib/studio';
import { errorMessage } from '../lib/errors';
import { getApiUrl } from '../config';

// created_at / last_used_at may be epoch seconds or an ISO string.
function fmtDate(value, lang) {
  if (!value) return '';
  const d = typeof value === 'number' ? new Date(value < 1e12 ? value * 1000 : value) : new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString(lang === 'vi' ? 'vi-VN' : 'en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// The full key, shown once. Everything the person needs to not lose it is here:
// a warning, a select-on-focus box and a Copy button.
function FreshKey({ fresh, onDone }) {
  const { t } = useLang();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(fresh.key);
      setCopied(true);
    } catch (_) {
      setCopied(false);   // blocked clipboard: the box is selectable by hand
    }
  };

  return (
    <div className="rounded-input border border-warn/40 bg-warn/10 p-4 space-y-3" role="status">
      <p className="text-sm text-ink font-medium">{t('apikeys.new.title')}{fresh.name ? ` · ${fresh.name}` : ''}</p>
      <p className="text-sm text-ink2 flex gap-2"><AlertTriangle size={16} className="mt-0.5 shrink-0 text-warn" />{t('apikeys.new.warn')}</p>
      <div className="flex flex-col sm:flex-row gap-2">
        <input readOnly aria-label={t('apikeys.new.title')} value={fresh.key}
          onFocus={(e) => e.target.select()}
          className="input-field font-mono text-xs flex-1 min-w-0" />
        <button type="button" onClick={copy} className="btn-ghost px-4 py-2 shrink-0">
          {copied ? <Check size={15} className="text-ok" /> : <Copy size={15} />}
          {copied ? t('apikeys.copied') : t('apikeys.copy')}
        </button>
      </div>
      <button type="button" onClick={onDone} className="btn-primary px-4 py-2">{t('apikeys.saved')}</button>
    </div>
  );
}

function KeyRow({ item, lang, t, onRevoke }) {
  return (
    <li className="py-3 flex items-center gap-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm text-ink truncate">{item.name || t('apikeys.unnamed')}</p>
        <p className="text-xs text-muted mt-0.5 flex flex-wrap gap-x-3">
          <span className="font-mono">{item.prefix}…</span>
          <span>{t('apikeys.created', { date: fmtDate(item.created_at, lang) })}</span>
          <span>{item.last_used_at ? t('apikeys.lastused', { date: fmtDate(item.last_used_at, lang) }) : t('apikeys.neverused')}</span>
        </p>
      </div>
      <button type="button" onClick={() => onRevoke(item)} className="btn-quiet px-3 py-1.5 text-sm shrink-0">
        <Trash2 size={14} /> {t('apikeys.revoke')}
      </button>
    </li>
  );
}

function UsageHint({ t }) {
  const mcp = new URL(getApiUrl('/mcp'), window.location.origin).href;
  return (
    <div className="mt-6 pt-5 border-t border-rule space-y-2">
      <p className="eyebrow">{t('apikeys.usage.title')}</p>
      <p className="text-xs text-muted">{t('apikeys.usage.api')}</p>
      <pre className="rounded-input bg-paper3 px-3 py-2 text-xs text-ink2 overflow-x-auto"><code>Authorization: Bearer vsk_...</code></pre>
      <p className="text-xs text-muted">{t('apikeys.usage.mcp')}</p>
      <pre className="rounded-input bg-paper3 px-3 py-2 text-xs text-ink2 overflow-x-auto"><code>{mcp}</code></pre>
    </div>
  );
}

export default function StudioApiKeysCard() {
  const { t, lang } = useLang();
  const [keys, setKeys] = useState(null);       // null while loading
  const [allowed, setAllowed] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [fresh, setFresh] = useState(null);     // { key, name } until dismissed
  const [revoking, setRevoking] = useState(null);   // the key row being confirmed
  const [revokeBusy, setRevokeBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await keysApi.list();
      setKeys(res.items || []);
      setAllowed(res.allowed !== false);
      setLoadError('');
    } catch (err) {
      if (err.code === 'plan_required') { setAllowed(false); setKeys([]); }
      else { setKeys((k) => k || []); setLoadError(errorMessage(t, err)); }
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true); setError('');
    try {
      const res = await keysApi.create(name.trim());
      setFresh({ key: res.key, name: res.name });
      setName('');
      await load();
    } catch (err) {
      if (err.code === 'plan_required') setAllowed(false);   // 402: the plan has no API access
      else setError(errorMessage(t, err));
    } finally { setBusy(false); }
  };

  const revoke = async () => {
    if (!revoking) return;
    setRevokeBusy(true); setError('');
    try {
      await keysApi.revoke(revoking.id);
      setRevoking(null);
      await load();
    } catch (err) {
      setRevoking(null);
      setError(errorMessage(t, err));
    } finally { setRevokeBusy(false); }
  };

  return (
    <section className="card p-5 sm:p-6">
      <h3 className="font-display text-lg text-ink flex items-center gap-2"><KeyRound size={18} className="text-brass" />{t('apikeys.title')}</h3>
      <p className="text-sm text-muted mt-1">{t('apikeys.sub')}</p>

      <div className="mt-5 space-y-4">
        {fresh && <FreshKey fresh={fresh} onDone={() => setFresh(null)} />}

        {allowed ? (
          <form onSubmit={create} className="flex flex-col sm:flex-row sm:items-end gap-3">
            <label className="block flex-1 min-w-0">
              <span className="eyebrow">{t('apikeys.name')}</span>
              <input className="input-field mt-1.5" value={name} maxLength={60} placeholder={t('apikeys.name.ph')}
                autoComplete="off" onChange={(e) => setName(e.target.value)} />
            </label>
            <button type="submit" disabled={busy} className="btn-primary px-5 py-2.5 shrink-0">
              {busy && <Loader2 size={15} className="animate-spin" />} {t('apikeys.create')}
            </button>
          </form>
        ) : (
          <div className="rounded-input bg-paper3 px-4 py-3 text-sm text-ink2 flex flex-wrap items-center gap-x-4 gap-y-2">
            <span>{t('apikeys.upgrade')}</span>
            <a href="#/pricing" className="text-ink font-medium underline underline-offset-4">{t('apikeys.upgrade.cta')}</a>
          </div>
        )}

        {error && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3 py-2">{error}</p>}
        {loadError && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3 py-2">{loadError}</p>}

        {keys === null ? (
          <Loader2 size={18} className="animate-spin text-muted" />
        ) : keys.length === 0 ? (
          <p className="text-sm text-muted">{t('apikeys.empty')}</p>
        ) : (
          <ul className="divide-y divide-rule">
            {keys.map((item) => <KeyRow key={item.id} item={item} lang={lang} t={t} onRevoke={setRevoking} />)}
          </ul>
        )}
      </div>

      <UsageHint t={t} />

      <Modal isOpen={!!revoking} onClose={revokeBusy ? undefined : () => setRevoking(null)} size="sm" title={t('apikeys.revoke')}
        footer={(
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-quiet px-4 py-2" onClick={() => setRevoking(null)} disabled={revokeBusy}>{t('common.cancel')}</button>
            <button type="button" className="btn-danger px-5 py-2" onClick={revoke} disabled={revokeBusy}>
              {revokeBusy && <Loader2 size={15} className="animate-spin" />} {t('apikeys.revoke')}
            </button>
          </div>
        )}>
        <p className="text-sm text-ink2">{t('apikeys.revoke.confirm', { name: revoking?.name || revoking?.prefix || '' })}</p>
      </Modal>
    </section>
  );
}
