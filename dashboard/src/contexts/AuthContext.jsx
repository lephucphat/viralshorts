// Auth + billing session state for cloud mode.
// - Reads /api/config to learn whether billing is enabled at all.
// - Handles the magic-link and Google OAuth redirect hashes.
// - Exposes the current user, plan and minute balance to the app.
// When billingEnabled is false the provider is inert and the app behaves as the
// classic BYOK dashboard.
import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { getApiUrl } from '../config';
import { apiFetch, apiJson, getToken, setToken, clearToken, SESSION_EXPIRED_EVENT } from '../lib/api';
import { takeRememberedRoute, clearRememberedRoute } from '../lib/returnTo';
import { isStudioHash } from '../lib/hashRoute';
import { track, identify, reset as resetAnalytics } from '../lib/analytics';
import { report as reportAttribution } from '../lib/attribution';

const AuthContext = createContext(null);
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [config, setConfig] = useState({ billingEnabled: false, googleAuthEnabled: false });
  const [me, setMe] = useState(null);           // /api/me payload, or null when signed out
  const [loading, setLoading] = useState(true);
  const [signingIn, setSigningIn] = useState(false);
  // Read inside event handlers and async continuations that run before React has
  // re-rendered with the fetched config.
  const accountsRef = useRef(false);

  const refreshMe = useCallback(async () => {
    if (!getToken()) { setMe(null); return null; }
    try {
      const data = await apiJson('/api/me');
      setMe(data);
      // Same profileId (user uuid) the server-side events use.
      identify(data?.user, { plan: data?.plan || 'free' });
      return data;
    } catch (e) {
      // Only a 401 means the token is dead. A network blip or a 5xx says nothing
      // about the session, so the token stays and a reload can recover.
      if (e?.status === 401) {
        clearToken();
        setMe(null);
      }
      return null;
    }
  }, []);

  // The server refused the session (api.js already cleared the token and
  // remembered the route). Show the signed-out state and go to the sign-in page.
  useEffect(() => {
    const onExpired = () => {
      setMe(null);
      resetAnalytics();
      if (!accountsRef.current) return;
      const path = (window.location.hash || '').split('?')[0];
      // The email-link pages work without a session and must stay where they are
      // (confirming a new address ends every session, then shows "sign in again").
      const open = ['#/login', '#/register', '#/forgot', '#/reset', '#/verify'];
      if (isStudioHash(path) && !open.includes(path)) {
        window.location.hash = '#/login';
      }
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, []);

  // Handle auth redirect hashes: #/auth/verify?ml=... and #/auth/callback?token=...
  const handleAuthHash = useCallback(async () => {
    const hash = window.location.hash || '';
    const match = hash.match(/^#\/auth\/(verify|callback)\??(.*)$/);
    if (!match) return false;
    const [, kind, query] = match;
    const params = new URLSearchParams(query);

    setSigningIn(true);
    let destination = '#app';
    try {
      if (kind === 'callback') {
        const token = params.get('token');
        if (token) {
          setToken(token);
          // Scrub the token from the URL immediately (replaceState, no new
          // history entry) so the bearer token isn't left reachable via Back.
          try {
            window.history.replaceState(null, document.title,
              window.location.pathname + window.location.search);
          } catch (_) { /* ignore */ }
        }
      } else if (kind === 'verify') {
        const ml = params.get('ml');
        if (ml) {
          const data = await apiJson('/api/auth/magic-link/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: ml }),
          });
          if (data.token) setToken(data.token);
        }
      }
      const signedInMe = await refreshMe();
      // This handler only runs on the auth redirect, so a resolved user here is
      // a fresh sign-in / sign-up — the top of the conversion funnel.
      if (signedInMe?.user) {
        track('Signup', { props: { method: kind === 'verify' ? 'magic_link' : 'google' } });
        // Server-side twin of the Signup event: the one place we learn which
        // channel produced an account. Awaited but never allowed to throw.
        await reportAttribution(apiJson);
      }
      // Everyone lands in the app. First-time (unpaid) sign-in gets the Clip
      // Generator tutorial, not a pricing dump — they need one successful job
      // before the rest of the tools unlock. os_welcomed keeps this once-only
      // even if they skip the tutorial.
      const paid = ['starter', 'creator', 'pro'].includes(signedInMe?.plan);
      let welcomed = false;
      try { welcomed = localStorage.getItem('os_welcomed') === '1'; } catch (_) { /* ignore */ }
      if (signedInMe?.user && !paid && !welcomed) {
        try {
          localStorage.setItem('os_show_clip_tutorial', '1');
          localStorage.setItem('os_welcomed', '1');
        } catch (_) { /* ignore */ }
      }
    } catch (e) {
      // fall through — user lands signed-out
    } finally {
      setSigningIn(false);
      // Clear the sensitive hash, land wherever we resolved above. Own accounts
      // go back to the route the person was on when their session ended.
      const back = accountsRef.current && getToken() ? takeRememberedRoute() : '';
      window.location.hash = back || destination;
    }
    return true;
  }, [refreshMe]);

  useEffect(() => {
    (async () => {
      try {
        const cfg = await (await fetch(getApiUrl('/api/config'))).json();
        accountsRef.current = !!cfg.accountsEnabled;
        setConfig(cfg);
        if (cfg.billingEnabled) {
          const handled = await handleAuthHash();
          if (!handled) await refreshMe();
        } else if (cfg.accountsEnabled) {
          // Own accounts: a password session, or the token Google's callback
          // left in the hash (#/auth/callback?token=...).
          const handled = await handleAuthHash();
          if (!handled) await refreshMe();
        }
      } catch (_) { /* config fetch failed — stay in BYOK */ }
      setLoading(false);
    })();
  }, [handleAuthHash, refreshMe]);

  const requestMagicLink = useCallback(async (email) => {
    const res = await apiFetch('/api/auth/magic-link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    if (res.status === 429) throw new Error('Too many attempts. Try again in a few minutes.');
    if (!res.ok) throw new Error('Could not send sign-in link.');
    return true;
  }, []);

  const loginWithGoogle = useCallback(() => {
    window.location.href = getApiUrl('/api/auth/google');
  }, []);

  const logout = useCallback(() => {
    clearToken();
    clearRememberedRoute();
    setMe(null);
    resetAnalytics();
  }, []);

  // Own accounts (ACCOUNTS_ENABLED): email + password against /api/auth/*.
  // Throws an Error whose `code` is the server's machine-readable reason. The
  // message is never meant for display (it is the server's English): forms map the
  // code to a translated sentence with lib/errors.js.
  const passwordAuth = useCallback(async (path, payload) => {
    const res = await apiFetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    let data = null;
    try { data = await res.json(); } catch (_) { /* non-JSON error page */ }
    if (!res.ok) {
      const d = data?.detail;
      // FastAPI validation failures (422) arrive as a list with no error code.
      const err = new Error((d && d.message) || (typeof d === 'string' ? d : '') || `http_${res.status}`);
      err.code = (d && d.error) || (res.status === 422 ? 'invalid_input' : `http_${res.status}`);
      err.status = res.status;
      throw err;
    }
    setToken(data.token);
    await refreshMe();
    return data.user;
  }, [refreshMe]);

  const loginWithPassword = useCallback(
    (email, password) => passwordAuth('/api/auth/login', { email, password }), [passwordAuth]);
  const registerWithPassword = useCallback(
    (email, password, name, lang, acceptTerms = false) =>
      passwordAuth('/api/auth/register', { email, password, name, lang, accept_terms: !!acceptTerms }),
    [passwordAuth]);

  const value = {
    accountsEnabled: !!config.accountsEnabled,
    loginWithPassword,
    registerWithPassword,
    usage: me?.usage || null,
    verificationRequired: !!me?.verification_required,
    billingEnabled: config.billingEnabled,
    localLlm: config.localLlm || null,
    googleAuthEnabled: config.googleAuthEnabled,
    jobRetentionSeconds: config.jobRetentionSeconds || null,
    loading,
    signingIn,
    user: me?.user || null,
    me,
    plan: me?.plan || null,
    entitled: !!me?.entitled,
    minutes: me?.minutes || null,
    isSignedIn: !!me?.user,
    // Managed = signed-in AND entitled (active plan or top-up credit).
    isManaged: !!(config.billingEnabled && me?.entitled),
    refreshMe,
    requestMagicLink,
    loginWithGoogle,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
