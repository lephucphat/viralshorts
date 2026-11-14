import { useEffect, useMemo, useState } from 'react';
import { Check, Loader2, Clapperboard, Palette, Captions, Sparkles, Moon, Sun, Monitor, Globe } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';
import { useTheme } from '../contexts/ThemeContext';
import GoogleButton from '../components/auth/GoogleButton';
import PasswordField from '../components/auth/PasswordField';
import { passwordStrength } from '../lib/password';
import { errorMessage } from '../lib/errors';
import { takeRememberedRoute } from '../lib/returnTo';

const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/;
const THEME_NEXT = { light: 'dark', dark: 'system', system: 'light' };

// A server-side or Google error that arrived in the URL (?error=...). Reading
// is pure (React may run an initialiser twice); scrubbing happens in an effect.
function readUrlError() {
  try {
    return new URLSearchParams(window.location.hash.split('?')[1] || '').get('error') || '';
  } catch (_) { return ''; }
}

// "Terms" and "Privacy" as links to the static legal pages. A new tab, so a
// half-filled form is never lost.
function LegalLinks({ short = false, t }) {
  const cls = 'text-ink underline underline-offset-4';
  return (
    <>
      <a className={cls} href="/terms" target="_blank" rel="noopener noreferrer">{t(short ? 'terms.tos.short' : 'terms.tos')}</a>
      {' '}{t('terms.and')}{' '}
      <a className={cls} href="/privacy" target="_blank" rel="noopener noreferrer">{t('terms.privacy')}</a>
    </>
  );
}

function BrandPanel({ t }) {
  const points = [
    [Clapperboard, 'auth.panel.p1'],
    [Captions, 'auth.panel.p2'],
    [Palette, 'auth.panel.p3'],
  ];
  return (
    <aside className="hidden lg:flex flex-col justify-between w-[44%] max-w-xl bg-paper2 border-r border-rule p-12 xl:p-16">
      <a href="#landing" className="flex items-center gap-2.5 w-fit">
        <img src="/logo-viralshorts.png" alt="" className="w-8 h-8 rounded-input border border-rule" />
        <span className="text-lg font-semibold tracking-tight text-ink">ViralShorts</span>
      </a>

      <div>
        <h2 className="font-display text-4xl xl:text-5xl leading-[1.1] text-ink">{t('auth.panel.title')}</h2>
        <ul className="mt-8 space-y-4">
          {points.map((point) => {
            const Icon = point[0];
            return (
              <li key={point[1]} className="flex items-start gap-3.5 text-ink2">
                <span className="mt-0.5 w-8 h-8 rounded-input bg-paper3 flex items-center justify-center shrink-0">
                  <Icon size={16} className="text-brass" />
                </span>
                <span className="leading-snug pt-1">{t(point[1])}</span>
              </li>
            );
          })}
        </ul>
      </div>

      {/* A clip card, drawn in CSS: the product in one glance, nothing to load. */}
      <div className="flex items-end gap-4" aria-hidden="true">
        <div className="w-28 aspect-[9/16] rounded-2xl overflow-hidden relative border border-rule2"
          style={{ background: 'linear-gradient(160deg, #1f1f23, #6d5bff 130%)' }}>
          <span className="absolute top-2.5 left-2.5 text-[0.5625rem] font-semibold text-white/80 border border-white/40 rounded px-1">logo</span>
          <span className="absolute inset-x-2 bottom-[28%] text-center text-[0.6875rem] font-extrabold text-white leading-tight"
            style={{ textShadow: '0 1px 3px rgba(0,0,0,.8)' }}>
            {t('auth.panel.caption')} <span style={{ color: '#FFD700' }}>{t('auth.panel.captionword')}</span>
          </span>
        </div>
        <div className="pb-1">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-ink text-paper text-xs font-medium px-3 py-1.5">
            <Sparkles size={12} /> {t('auth.panel.score')} 92
          </span>
          <p className="text-xs text-muted mt-2 max-w-[11rem]">{t('auth.panel.scorehint')}</p>
        </div>
      </div>
    </aside>
  );
}

// One page for both forms: the two differ by a single field and a link, and a
// shared layout means switching between them never reflows the screen.
export default function AuthPage({ mode }) {
  const { t, lang, setLang } = useLang();
  const { mode: themeMode, setMode: setThemeMode } = useTheme();
  const { loginWithPassword, registerWithPassword, googleAuthEnabled } = useAuth();
  const isRegister = mode === 'register';
  const ThemeIcon = themeMode === 'dark' ? Moon : themeMode === 'light' ? Sun : Monitor;

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [touchedEmail, setTouchedEmail] = useState(false);
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [busy, setBusy] = useState(false);
  const [urlError] = useState(readUrlError);
  // Scrub it so a reload does not show a stale message.
  useEffect(() => {
    if (!urlError) return;
    try { window.history.replaceState(null, document.title, window.location.pathname + window.location.search + window.location.hash.split('?')[0]); } catch (_) { /* ignore */ }
  }, [urlError]);
  const [error, setError] = useState('');

  // Codes come from the server or from Google's redirect (?error=...); the
  // helper maps both to translated text and never shows the server's English.
  const shownError = error || (urlError ? errorMessage(t, { code: urlError }) : '');

  const emailOk = EMAIL_RE.test(email.trim());
  const strength = useMemo(() => passwordStrength(password), [password]);
  const emailProblem = touchedEmail && email.trim() && !emailOk;
  const canSubmit = !busy && emailOk && (isRegister ? strength > 0 && acceptTerms : password.length > 0);

  const submit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError('');
    try {
      if (isRegister) await registerWithPassword(email.trim(), password, name.trim(), lang, acceptTerms);
      else await loginWithPassword(email.trim(), password);
      // Back to where a lapsed session left off, else the library.
      window.location.hash = takeRememberedRoute() || '#/projects';
    } catch (err) {
      setError(errorMessage(t, err));
    } finally {
      setBusy(false);
    }
  };

  const strengthLabel = ['auth.strength.none', 'auth.strength.ok', 'auth.strength.good', 'auth.strength.strong'][strength];

  return (
    <div className="min-h-screen bg-paper flex">
      <BrandPanel t={t} />

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 px-4 sm:px-8 flex items-center justify-between shrink-0">
          <a href="#landing" className="lg:invisible flex items-center gap-2.5 min-w-0">
            <img src="/logo-viralshorts.png" alt="" className="w-7 h-7 rounded-input border border-rule" />
            <span className="text-lg font-semibold tracking-tight text-ink">ViralShorts</span>
          </a>
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => setThemeMode(THEME_NEXT[themeMode] || 'light')} aria-label={t('theme.tip')}
              className="p-2.5 rounded-full text-muted hover:text-ink hover:bg-paper3 transition-colors"><ThemeIcon size={17} /></button>
            <button type="button" onClick={() => setLang(lang === 'vi' ? 'en' : 'vi')}
              className="flex items-center gap-1.5 px-3 py-2 rounded-full text-sm text-muted hover:text-ink hover:bg-paper3 transition-colors">
              <Globe size={15} /> {t('lang.switch')}
            </button>
          </div>
        </header>

        <main className="flex-1 flex items-center justify-center px-4 sm:px-8 pb-12">
          <form onSubmit={submit} className="w-full max-w-sm space-y-5 animate-fade" noValidate>
            <div>
              <h1 className="font-display text-3xl text-ink">
                {isRegister ? t('auth.register.title') : t('auth.login.title')}
              </h1>
              <p className="text-sm text-muted mt-2">
                {isRegister ? t('auth.register.sub') : t('auth.login.sub')}
              </p>
            </div>

            <GoogleButton />
            {googleAuthEnabled && (
              <p className="text-xs text-muted -mt-2 text-center">
                {t('terms.google.pre')} <LegalLinks short t={t} />
              </p>
            )}
            {googleAuthEnabled && (
              <div className="flex items-center gap-3" role="separator">
                <span className="flex-1 border-t border-rule" />
                <span className="readout">{t('auth.or')}</span>
                <span className="flex-1 border-t border-rule" />
              </div>
            )}

            {shownError && (
              <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3.5 py-2.5">{shownError}</p>
            )}

            {isRegister && (
              <label className="block">
                <span className="eyebrow">{t('auth.name')}</span>
                <input className="input-field mt-1.5" value={name} onChange={(e) => setName(e.target.value)}
                  autoComplete="name" maxLength={80} />
              </label>
            )}

            <label className="block">
              <span className="eyebrow">{t('auth.email')}</span>
              <input className={`input-field mt-1.5 ${emailProblem ? '!border-danger' : ''}`} type="email" inputMode="email"
                value={email} onChange={(e) => setEmail(e.target.value)} onBlur={() => setTouchedEmail(true)}
                autoComplete="email" autoCapitalize="none" spellCheck={false}
                aria-invalid={emailProblem ? 'true' : undefined} placeholder="you@email.com" />
              {emailProblem && <span role="alert" className="text-xs text-danger mt-1.5 block">{t('auth.err.email')}</span>}
            </label>

            {!isRegister && (
              <p className="text-right -mb-2">
                <a className="text-xs text-muted hover:text-ink underline underline-offset-4" href="#/forgot">{t('auth.forgot.link')}</a>
              </p>
            )}
            <PasswordField label={t('auth.password')} value={password} onChange={setPassword}
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              hint={isRegister ? (
                <div>
                  <div className="flex gap-1.5" aria-hidden="true">
                    {[1, 2, 3].map((n) => (
                      <span key={n} className={`h-1 flex-1 rounded-full transition-colors ${strength >= n ? (strength === 1 ? 'bg-warn' : 'bg-ok') : 'bg-paper3'}`} />
                    ))}
                  </div>
                  <p className="text-xs mt-2 flex items-center gap-1.5 text-muted" aria-live="polite">
                    <Check size={13} className={strength > 0 ? 'text-ok' : 'opacity-40'} />
                    {t('auth.password.hint')}
                    {password && strength > 0 && <span className="ml-auto text-ink2">{t(strengthLabel)}</span>}
                  </p>
                </div>
              ) : null} />

            {isRegister && (
              <label className="flex items-start gap-2.5 text-sm text-ink2 cursor-pointer">
                <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-brass"
                  checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} />
                <span>{t('terms.accept.pre')} <LegalLinks t={t} /></span>
              </label>
            )}

            <button type="submit" disabled={!canSubmit} className="btn-primary w-full !py-3">
              {busy && <Loader2 size={16} className="animate-spin" />}
              {isRegister ? t('auth.register.cta') : t('auth.login.cta')}
            </button>

            <p className="text-sm text-muted text-center">
              {isRegister ? t('auth.have') : t('auth.new')}{' '}
              <a className="text-ink font-medium underline underline-offset-4" href={isRegister ? '#/login' : '#/register'}>
                {isRegister ? t('auth.login.cta') : t('auth.register.cta')}
              </a>
            </p>
          </form>
        </main>
      </div>
    </div>
  );
}
