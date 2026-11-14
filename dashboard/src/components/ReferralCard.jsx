import { useCallback, useEffect, useState } from 'react';
import { Check, Copy, Gift, Loader2 } from 'lucide-react';
import { useLang } from '../contexts/LangContext';
import { referralApi } from '../lib/studio';
import { errorMessage } from '../lib/errors';

const ERR = {
  invalid_code: 'ref.err.invalid_code', own_code: 'ref.err.own_code', already_referred: 'ref.err.already_referred',
  already_customer: 'ref.err.already_customer', referral_off: 'ref.err.referral_off',
};

// Account → "Refer a friend". Renders nothing while the program is off on this server.
export default function ReferralCard() {
  const { t } = useLang();
  const [info, setInfo] = useState(null);
  const [copied, setCopied] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState({ bad: false, text: '' });

  const load = useCallback(() => referralApi.get().then(setInfo).catch(() => setInfo({ enabled: false })), []);
  useEffect(() => { load(); }, [load]);

  if (!info?.enabled) return null;

  const link = `${window.location.origin}/#/register?ref=${info.code}`;
  const copy = async (what, text) => {
    try { await navigator.clipboard.writeText(text); setCopied(what); setTimeout(() => setCopied(''), 1800); } catch (_) { /* clipboard blocked */ }
  };

  const attach = async (e) => {
    e.preventDefault();
    setBusy(true); setMsg({ bad: false, text: '' });
    try {
      setInfo(await referralApi.attach(code.trim()));
      setCode('');
      setMsg({ bad: false, text: t('ref.attach.ok') });
    } catch (err) {
      const key = ERR[err?.code];
      setMsg({ bad: true, text: key ? t(key) : errorMessage(t, err) });
    } finally { setBusy(false); }
  };

  const stat = (label, value) => (
    <div className="rounded-input bg-paper2 border border-rule p-3 text-center">
      <p className="text-2xl font-display text-ink tabular-nums">{value}</p>
      <p className="text-xs text-muted mt-0.5">{label}</p>
    </div>
  );
  const row = (what, label, value) => (
    <div>
      <span className="eyebrow">{label}</span>
      <div className="flex gap-2 mt-1.5">
        <input className="input-field font-mono text-sm" readOnly value={value} onFocus={(e) => e.target.select()} aria-label={label} />
        <button type="button" className="btn-secondary !px-3.5 shrink-0" onClick={() => copy(what, value)}>
          {copied === what ? <Check size={15} /> : <Copy size={15} />} <span className="hidden sm:inline">{copied === what ? t('ref.copied') : t('ref.copy')}</span>
        </button>
      </div>
    </div>
  );

  const a = info.attached;
  return (
    <section className="card p-5 sm:p-6 lg:col-span-2">
      <div className="flex items-start gap-3">
        <span className="w-10 h-10 rounded-2xl bg-brand text-brassink flex items-center justify-center shadow-cta shrink-0" aria-hidden="true"><Gift size={18} /></span>
        <div>
          <h2 className="font-display text-lg text-ink">{t('ref.title')}</h2>
          <p className="text-sm text-muted mt-1">{t('ref.sub', { n: info.reward_credits })}</p>
        </div>
      </div>
      <div className="grid md:grid-cols-2 gap-6 mt-5">
        <div className="space-y-4 min-w-0">
          {row('code', t('ref.code'), info.code)}
          {row('link', t('ref.link'), link)}
          <div className="grid grid-cols-3 gap-3">
            {stat(t('ref.stats.invited'), info.invited)}
            {stat(t('ref.stats.rewarded'), info.rewarded)}
            {stat(t('ref.stats.credits'), info.credits_earned)}
          </div>
          <a href="/referral-terms" className="text-sm text-accent underline underline-offset-2 inline-block">{t('ref.terms')}</a>
        </div>
        <div className="space-y-3 min-w-0">
          {a ? (
            <p className={`text-sm rounded-input px-3 py-2.5 ${a.status === 'void' ? 'bg-warn/10 text-warn' : 'bg-ok/10 text-ok'}`}>
              {a.status === 'rewarded' ? t('ref.attached.rewarded', { n: a.reward_credits })
                : a.status === 'void' ? t('ref.attached.void')
                  : t('ref.attached.pending', { n: info.reward_credits })}
            </p>
          ) : info.can_attach ? (
            <form onSubmit={attach} className="space-y-3">
              <h3 className="text-sm font-semibold text-ink">{t('ref.have')}</h3>
              <p className="text-xs text-muted">{t('ref.have.sub')}</p>
              <input className="input-field font-mono" value={code} autoComplete="off" autoCapitalize="characters" spellCheck={false}
                aria-label={t('ref.input')} placeholder="VS-XXXXXXX" onChange={(e) => setCode(e.target.value)} />
              <button type="submit" className="btn-primary px-5 py-2.5" disabled={busy || !code.trim()}>
                {busy && <Loader2 size={15} className="animate-spin" />} {t('ref.attach')}
              </button>
            </form>
          ) : null}
          {msg.text && <p role={msg.bad ? 'alert' : 'status'} className={`text-sm ${msg.bad ? 'text-danger' : 'text-ok'}`}>{msg.text}</p>}
        </div>
      </div>
    </section>
  );
}
