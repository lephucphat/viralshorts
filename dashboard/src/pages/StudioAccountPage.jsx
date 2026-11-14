import { useState } from 'react';
import { Check, Download, Loader2, LogOut } from 'lucide-react';
import StudioShell from '../StudioShell';
import Modal from '../components/ui/Modal';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';
import { accountApi } from '../lib/studio';
import { setToken } from '../lib/api';
import PasswordField from '../components/auth/PasswordField';
import { passwordStrength } from '../lib/password';
import BillingSection from '../components/BillingSection';
import StudioApiKeysCard from '../components/StudioApiKeysCard';
import ReferralCard from '../components/ReferralCard';
import { errorMessage } from '../lib/errors';

function Section({ title, sub, children }) {
  return (
    <section className="card p-5 sm:p-6">
      <h2 className="font-display text-lg text-ink">{title}</h2>
      {sub && <p className="text-sm text-muted mt-1">{sub}</p>}
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Message({ kind, children }) {
  if (!children) return null;
  return kind === 'error'
    ? <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3 py-2 mt-3">{children}</p>
    : <p role="status" className="text-sm text-ok mt-3 flex items-center gap-1.5"><Check size={14} /> {children}</p>;
}

export default function StudioAccountPage() {
  const { t, lang, setLang } = useLang();
  const { user, usage, refreshMe, logout } = useAuth();

  const hasPassword = user?.has_password !== false;
  const [name, setName] = useState(user?.name || '');
  const [profileMsg, setProfileMsg] = useState({ kind: '', text: '' });
  const [savingProfile, setSavingProfile] = useState(false);

  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [pwMsg, setPwMsg] = useState({ kind: '', text: '' });
  const [savingPw, setSavingPw] = useState(false);

  const [deleting, setDeleting] = useState(false);
  const [deletePw, setDeletePw] = useState('');
  const [deleteErr, setDeleteErr] = useState('');
  const [deleteBusy, setDeleteBusy] = useState(false);

  const [newEmail, setNewEmail] = useState('');
  const [emailConfirm, setEmailConfirm] = useState('');   // password, or the current email for a Google-only account
  const [emailMsg, setEmailMsg] = useState({ kind: '', text: '' });
  const [savingEmail, setSavingEmail] = useState(false);

  const [devicesMsg, setDevicesMsg] = useState({ kind: '', text: '' });
  const [devicesBusy, setDevicesBusy] = useState('');     // '' | 'logout' | 'export'

  // A wrong "password" is a wrong typed email for an account that has none.
  const wrongSecret = { bad_credentials: hasPassword ? 'account.password.wrong' : 'account.email.wrong' };

  const saveProfile = async (e) => {
    e.preventDefault();
    setSavingProfile(true); setProfileMsg({ kind: '', text: '' });
    try {
      await accountApi.update({ name: name.trim(), lang });
      await refreshMe();
      setProfileMsg({ kind: 'ok', text: t('common.saved') });
    } catch (err) { setProfileMsg({ kind: 'error', text: errorMessage(t, err) }); }
    finally { setSavingProfile(false); }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    setSavingPw(true); setPwMsg({ kind: '', text: '' });
    try {
      const res = await accountApi.changePassword(current, next);
      setToken(res.token);                 // the old token just stopped working
      setCurrent(''); setNext('');
      await refreshMe();                 // a Google-only account now has a password
      setPwMsg({ kind: 'ok', text: t('account.password.done') });
    } catch (err) {
      setPwMsg({ kind: 'error', text: errorMessage(t, err, { bad_credentials: 'account.password.wrong' }) });
    } finally { setSavingPw(false); }
  };

  const deleteAccount = async () => {
    setDeleteBusy(true); setDeleteErr('');
    try {
      await accountApi.remove(deletePw);
      logout();
      window.location.hash = '#/deleted';
    } catch (err) {
      setDeleteErr(errorMessage(t, err, wrongSecret));
      setDeleteBusy(false);
    }
  };

  const changeEmail = async (e) => {
    e.preventDefault();
    setSavingEmail(true); setEmailMsg({ kind: '', text: '' });
    const target = newEmail.trim();
    try {
      await accountApi.changeEmail(target, emailConfirm);
      setNewEmail(''); setEmailConfirm('');
      setEmailMsg({ kind: 'ok', text: t('account.email.sent', { email: target }) });
    } catch (err) {
      setEmailMsg({ kind: 'error', text: errorMessage(t, err, wrongSecret) });
    } finally { setSavingEmail(false); }
  };

  const logoutAll = async () => {
    setDevicesBusy('logout'); setDevicesMsg({ kind: '', text: '' });
    try {
      const res = await accountApi.logoutAll();
      setToken(res.token);               // every older token just stopped working
      await refreshMe();
      setDevicesMsg({ kind: 'ok', text: t('account.logoutall.done') });
    } catch (err) {
      setDevicesMsg({ kind: 'error', text: errorMessage(t, err) });
    } finally { setDevicesBusy(''); }
  };

  const exportData = async () => {
    setDevicesBusy('export'); setDevicesMsg({ kind: '', text: '' });
    try {
      const blob = await accountApi.exportData();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'viralshorts-my-data.json';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setDevicesMsg({ kind: 'ok', text: t('account.export.done') });
    } catch (err) {
      setDevicesMsg({ kind: 'error', text: errorMessage(t, err) });
    } finally { setDevicesBusy(''); }
  };

  const pct = usage && !usage.unlimited ? Math.min(100, Math.round((usage.used / Math.max(1, usage.limit)) * 100)) : 0;

  return (
    <StudioShell active="account">
      <h1 className="font-display text-3xl text-ink mb-8">{t('account.title')}</h1>
      <div className="grid lg:grid-cols-2 gap-6 items-start max-w-5xl">
        {usage?.paid && <BillingSection />}
        {usage?.paid && <ReferralCard />}

        {!usage?.paid && (
        <Section title={t('account.usage')} sub={t('account.usage.sub')}>
          {usage ? (
            usage.unlimited ? (
              <p className="text-ink2">{t('account.usage.unlimited', { used: usage.used })}</p>
            ) : (
              <>
                <p className="text-3xl font-display text-ink tabular-nums">
                  {usage.remaining} <span className="text-base text-muted">/ {usage.limit} {t('account.minutes')}</span>
                </p>
                <div className="h-2 mt-4 rounded-full bg-paper3 overflow-hidden">
                  <div className="h-full bg-brass rounded-full" style={{ width: `${pct}%` }} />
                </div>
                <p className="text-xs text-muted mt-2">{t('account.usage.used', { used: usage.used })}</p>
              </>
            )
          ) : <Loader2 size={18} className="animate-spin text-muted" />}
        </Section>
        )}

        <Section title={t('account.profile')}>
          <form onSubmit={saveProfile} className="space-y-4">
            <label className="block">
              <span className="eyebrow">{t('auth.email')}</span>
              <input className="input-field mt-1.5 opacity-70" value={user?.email || ''} readOnly />
              {user?.has_google && (
                <span className="text-xs text-muted mt-1.5 flex items-center gap-1.5">
                  <Check size={13} className="text-ok" /> {t('account.google')}
                </span>
              )}
            </label>
            <label className="block">
              <span className="eyebrow">{t('auth.name')}</span>
              <input className="input-field mt-1.5" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="block">
              <span className="eyebrow">{t('account.language')}</span>
              <select className="input-field mt-1.5" value={lang} onChange={(e) => setLang(e.target.value)}>
                <option value="vi">Tiếng Việt</option>
                <option value="en">English</option>
              </select>
            </label>
            <button type="submit" className="btn-primary px-5 py-2.5" disabled={savingProfile}>
              {savingProfile && <Loader2 size={15} className="animate-spin" />} {t('common.save')}
            </button>
            <Message kind={profileMsg.kind}>{profileMsg.text}</Message>
          </form>
        </Section>

        <Section title={t('account.email.title')} sub={t('account.email.sub')}>
          <form onSubmit={changeEmail} className="space-y-4">
            <label className="block">
              <span className="eyebrow">{t('account.email.new')}</span>
              <input className="input-field mt-1.5" type="email" inputMode="email" autoComplete="email"
                autoCapitalize="none" spellCheck={false} value={newEmail} onChange={(e) => setNewEmail(e.target.value)} />
            </label>
            {hasPassword ? (
              <PasswordField label={t('account.email.password')} value={emailConfirm} onChange={setEmailConfirm}
                autoComplete="current-password" />
            ) : (
              <label className="block">
                <span className="eyebrow">{t('account.email.confirm')}</span>
                <input className="input-field mt-1.5" type="email" autoComplete="off" value={emailConfirm}
                  placeholder={user?.email || t('auth.email')} onChange={(e) => setEmailConfirm(e.target.value)} />
              </label>
            )}
            <button type="submit" className="btn-primary px-5 py-2.5" disabled={savingEmail || !newEmail.trim() || !emailConfirm}>
              {savingEmail && <Loader2 size={15} className="animate-spin" />} {t('account.email.cta')}
            </button>
            <Message kind={emailMsg.kind}>{emailMsg.text}</Message>
          </form>
        </Section>

        <Section title={hasPassword ? t('account.password') : t('account.password.set')}
          sub={hasPassword ? undefined : t('account.password.set.sub')}>
          <form onSubmit={changePassword} className="space-y-4">
            {hasPassword && (
              <PasswordField label={t('account.password.current')} value={current} onChange={setCurrent}
                autoComplete="current-password" />
            )}
            <PasswordField label={t('account.password.new')} value={next} onChange={setNext}
              autoComplete="new-password"
              hint={<span className="text-xs text-muted block">{t('auth.password.hint')}</span>} />
            <button type="submit" className="btn-primary px-5 py-2.5"
              disabled={savingPw || (hasPassword && !current) || passwordStrength(next) === 0}>
              {savingPw && <Loader2 size={15} className="animate-spin" />}
              {hasPassword ? t('account.password.cta') : t('account.password.set.cta')}
            </button>
            <Message kind={pwMsg.kind}>{pwMsg.text}</Message>
          </form>
        </Section>

        <Section title={t('account.sessions.title')} sub={t('account.sessions.sub')}>
          <div className="flex flex-wrap gap-3">
            <button type="button" className="btn-ghost px-5 py-2.5" onClick={logoutAll} disabled={!!devicesBusy}>
              {devicesBusy === 'logout' ? <Loader2 size={15} className="animate-spin" /> : <LogOut size={15} />} {t('account.logoutall')}
            </button>
            <button type="button" className="btn-ghost px-5 py-2.5" onClick={exportData} disabled={!!devicesBusy}>
              {devicesBusy === 'export' ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />} {t('account.export')}
            </button>
          </div>
          <Message kind={devicesMsg.kind}>{devicesMsg.text}</Message>
        </Section>

        <h2 className="lg:col-span-2 font-display text-xl text-ink mt-4">{t('account.api.section')}</h2>
        <div className="lg:col-span-2"><StudioApiKeysCard /></div>

        <Section title={t('account.danger')} sub={t('account.danger.sub')}>
          <button type="button" className="btn-danger px-5 py-2.5" onClick={() => { setDeleting(true); setDeletePw(''); setDeleteErr(''); }}>
            {t('account.delete')}
          </button>
        </Section>
      </div>

      <Modal isOpen={deleting} onClose={deleteBusy ? undefined : () => setDeleting(false)} size="sm" title={t('account.delete.title')}
        footer={(
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-quiet px-4 py-2" onClick={() => setDeleting(false)} disabled={deleteBusy}>{t('common.cancel')}</button>
            <button type="button" className="btn-danger px-5 py-2" disabled={!deletePw || deleteBusy} onClick={deleteAccount}>
              {deleteBusy && <Loader2 size={15} className="animate-spin" />} {t('account.delete.cta')}
            </button>
          </div>
        )}>
        <p className="text-sm text-ink2 mb-4">{hasPassword ? t('account.delete.body') : t('account.delete.body.email')}</p>
        {hasPassword ? (
          <PasswordField label={t('auth.password')} value={deletePw} onChange={setDeletePw}
            autoComplete="current-password" autoFocus />
        ) : (
          <input className="input-field" type="email" autoComplete="off" value={deletePw}
            placeholder={user?.email || t('auth.email')} onChange={(e) => setDeletePw(e.target.value)} autoFocus />
        )}
        <Message kind="error">{deleteErr}</Message>
      </Modal>
    </StudioShell>
  );
}
