import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';
import { recoveryApi } from '../lib/studio';
import { setToken } from '../lib/api';
import PasswordField from '../components/auth/PasswordField';
import { passwordStrength } from '../lib/password';
import { errorMessage } from '../lib/errors';

const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/;

// The token lives in the URL hash, which never reaches server logs. Read it once.
const readToken = () => {
  try { return new URLSearchParams(window.location.hash.split('?')[1] || '').get('token') || ''; } catch (_) { return ''; }
};

// Scrub the token from the address bar once it is in memory, so Back or a shared
// screenshot cannot leak a live link.
const scrubToken = (route) => {
  try { window.history.replaceState(null, document.title, window.location.pathname + window.location.search + route); } catch (_) { /* ignore */ }
};

function Frame({ title, sub, children }) {
  return (
    <div className="min-h-screen bg-paper flex flex-col">
      <header className="h-16 px-4 sm:px-8 flex items-center shrink-0">
        <a href="#landing" className="flex items-center gap-2.5">
          <img src="/logo-viralshorts.png" alt="" className="w-7 h-7 rounded-input border border-rule" />
          <span className="text-lg font-semibold tracking-tight text-ink">ViralShorts</span>
        </a>
      </header>
      <main className="flex-1 flex items-center justify-center px-4 sm:px-8 pb-16">
        <div className="w-full max-w-sm space-y-5 animate-fade">
          <div>
            <h1 className="font-display text-3xl text-ink">{title}</h1>
            {sub && <p className="text-sm text-muted mt-2">{sub}</p>}
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}

function Forgot() {
  const { t } = useLang();
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const ok = EMAIL_RE.test(email.trim());

  const submit = async (e) => {
    e.preventDefault();
    if (!ok || busy) return;
    setBusy(true); setError('');
    try { await recoveryApi.forgot(email.trim()); setSent(true); }
    catch (err) { setError(errorMessage(t, err)); }
    finally { setBusy(false); }
  };

  return (
    <Frame title={t('auth.forgot.title')} sub={t('auth.forgot.sub')}>
      {sent ? (
        <p role="status" className="text-sm text-ok flex gap-2"><Check size={16} className="mt-0.5 shrink-0" />{t('auth.forgot.sent')}</p>
      ) : (
        <form onSubmit={submit} className="space-y-5" noValidate>
          {error && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3.5 py-2.5">{error}</p>}
          <label className="block">
            <span className="eyebrow">{t('auth.email')}</span>
            <input className="input-field mt-1.5" type="email" inputMode="email" autoComplete="email" autoFocus
              autoCapitalize="none" spellCheck={false} value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <button type="submit" disabled={!ok || busy} className="btn-primary w-full !py-3">
            {busy && <Loader2 size={16} className="animate-spin" />} {t('auth.forgot.cta')}
          </button>
        </form>
      )}
      <p className="text-sm text-center"><a className="text-ink font-medium underline underline-offset-4" href="#/login">{t('auth.forgot.back')}</a></p>
    </Frame>
  );
}

function Reset() {
  const { t } = useLang();
  const { refreshMe } = useAuth();
  const token = useRef(readToken()).current;
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [invalid, setInvalid] = useState(!token);
  const [error, setError] = useState('');
  const strength = useMemo(() => passwordStrength(password), [password]);

  useEffect(() => { if (token) scrubToken('#/reset'); }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    if (strength === 0 || busy) return;
    setBusy(true); setError('');
    try {
      const res = await recoveryApi.reset(token, password);
      setToken(res.token);            // the reset signs the person in, every older session is dead
      await refreshMe();
      window.location.hash = '#/projects';
    } catch (err) {
      if (err.code === 'invalid_token') setInvalid(true);
      else setError(errorMessage(t, err));
      setBusy(false);
    }
  };

  if (invalid) {
    return (
      <Frame title={t('auth.reset.title')}>
        <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3.5 py-2.5">{t('auth.reset.invalid')}</p>
        <a className="btn-primary w-full !py-3" href="#/forgot">{t('auth.reset.again')}</a>
      </Frame>
    );
  }
  return (
    <Frame title={t('auth.reset.title')}>
      <form onSubmit={submit} className="space-y-5">
        {error && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3.5 py-2.5">{error}</p>}
        <PasswordField label={t('account.password.new')} value={password} onChange={setPassword}
          autoComplete="new-password" autoFocus
          hint={<span className="text-xs text-muted block">{t('auth.password.hint')}</span>} />
        <button type="submit" disabled={strength === 0 || busy} className="btn-primary w-full !py-3">
          {busy && <Loader2 size={16} className="animate-spin" />} {t('auth.reset.cta')}
        </button>
      </form>
    </Frame>
  );
}

// An expired or used link: ask for a fresh one. The answer is the same whether or
// not the address has an account, so this never reveals who is registered.
function ResendForm() {
  const { t } = useLang();
  const { user } = useAuth();
  const [email, setEmail] = useState(user?.email || '');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const ok = EMAIL_RE.test(email.trim());

  const submit = async (e) => {
    e.preventDefault();
    if (!ok || busy) return;
    setBusy(true); setError('');
    try { await recoveryApi.resendFor(email.trim()); setSent(true); }
    catch (err) { setError(errorMessage(t, err)); }
    finally { setBusy(false); }
  };

  if (sent) {
    return <p role="status" className="text-sm text-ok flex gap-2"><Check size={16} className="mt-0.5 shrink-0" />{t('auth.verify.resend.sent')}</p>;
  }
  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <p className="text-sm text-muted">{t('auth.verify.resend.sub')}</p>
      {error && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3.5 py-2.5">{error}</p>}
      <label className="block">
        <span className="eyebrow">{t('auth.email')}</span>
        <input className="input-field mt-1.5" type="email" inputMode="email" autoComplete="email"
          autoCapitalize="none" spellCheck={false} value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <button type="submit" disabled={!ok || busy} className="btn-primary w-full !py-3">
        {busy && <Loader2 size={16} className="animate-spin" />} {t('auth.verify.resend.cta')}
      </button>
    </form>
  );
}

function Verify() {
  const { t } = useLang();
  const { refreshMe, isSignedIn } = useAuth();
  const token = useRef(readToken()).current;
  const [state, setState] = useState(token ? 'working' : 'invalid');
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true;          // StrictMode runs effects twice; the token works once
    scrubToken('#/verify');
    // Confirming a NEW email address signs the person out everywhere, so the
    // session is re-read before the result is shown: signed in means a plain
    // sign-up confirmation, signed out means they must log in again.
    recoveryApi.verify(token)
      .then(async () => { await refreshMe(); setState('ok'); })
      .catch(() => setState('invalid'));
  }, [token, refreshMe]);

  return (
    <Frame
      title={t(state === 'ok' ? (isSignedIn ? 'auth.verify.ok' : 'auth.verify.done')
        : state === 'invalid' ? 'auth.verify.invalid' : 'auth.verify.working')}
      sub={state === 'ok' && !isSignedIn ? t('auth.verify.relogin') : undefined}>
      {state === 'working' && <Loader2 size={20} className="animate-spin text-muted" />}
      {state === 'invalid' && <ResendForm />}
      {state !== 'working' && (
        <a className={`w-full !py-3 ${state === 'ok' ? 'btn-primary' : 'btn-ghost'}`} href={isSignedIn ? '#/projects' : '#/login'}>
          {t(isSignedIn ? 'auth.verify.continue' : 'auth.login.cta')}
        </a>
      )}
    </Frame>
  );
}

export default function RecoveryPage({ mode }) {
  if (mode === 'reset') return <Reset />;
  if (mode === 'verify') return <Verify />;
  return <Forgot />;
}
