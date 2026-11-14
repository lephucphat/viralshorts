import { useState } from 'react';
import { Mail, Check, Loader2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';
import Modal from './ui/Modal';
import GoogleButton from './auth/GoogleButton';

// Sign-in dialog for the hosted (billing) edition: a magic link by email, or
// Google. The own-accounts edition uses the full AuthPage instead.
export default function LoginModal({ onClose }) {
  const { requestMagicLink, googleAuthEnabled } = useAuth();
  const { t } = useLang();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setBusy(true);
    setError('');
    try {
      await requestMagicLink(email.trim());
      setSent(true);
    } catch (err) {
      setError(err.message || t('login.err'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal isOpen onClose={onClose} eyebrow={t('login.eyebrow')} title={t('login.title')} size="sm">
      <p className="text-muted text-sm mb-6">{t('login.sub')}</p>

      {sent ? (
        <div className="text-center py-6" role="status">
          <span className="badge-ok px-3 py-1"><Check size={14} /> {t('login.sent')}</span>
          <p className="text-ink font-medium mt-4">{t('login.sent.title')}</p>
          <p className="text-muted text-sm mt-1.5">{t('login.sent.body', { email })}</p>
        </div>
      ) : (
        <div className="space-y-5">
          <GoogleButton />
          {googleAuthEnabled && (
            <div className="flex items-center gap-3" role="separator">
              <span className="flex-1 border-t border-rule" />
              <span className="readout">{t('auth.or')}</span>
              <span className="flex-1 border-t border-rule" />
            </div>
          )}

          <form onSubmit={submit} className="space-y-3" noValidate>
            <label className="block">
              <span className="eyebrow">{t('auth.email')}</span>
              <span className="relative block mt-1.5">
                <Mail size={17} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" />
                <input type="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@email.com" className="input-field pl-10" autoComplete="email" autoFocus />
              </span>
            </label>
            {error && <p role="alert" className="text-danger text-sm">{error}</p>}
            <button type="submit" disabled={busy || !email.trim()} className="btn-primary w-full !py-3">
              {busy ? <Loader2 size={18} className="animate-spin" /> : t('login.email.cta')}
            </button>
          </form>

          {/* The account is created by this button, so the terms have to be
              reachable from it: a magic-link signup never passes the footer. */}
          <p className="text-muted text-xs text-center leading-relaxed">
            {t('login.terms')}{' '}
            <a href="/terms" target="_blank" rel="noopener noreferrer" className="text-ink2 underline underline-offset-2 hover:text-brass transition-colors">{t('login.terms.tos')}</a>
            {' '}{t('login.terms.and')}{' '}
            <a href="/privacy" target="_blank" rel="noopener noreferrer" className="text-ink2 underline underline-offset-2 hover:text-brass transition-colors">{t('login.terms.privacy')}</a>.
          </p>
        </div>
      )}
    </Modal>
  );
}
