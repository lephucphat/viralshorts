// Centralized API client for cloud mode.
// Adds the Authorization: Bearer header from the stored session token, and turns
// a 402 (quota exceeded) into a typed QuotaError the UI can catch to prompt a top-up.
import { getApiUrl } from '../config';
import { rememberRoute } from './returnTo';

export const AUTH_TOKEN_KEY = 'viralshorts_auth';

export const getToken = () => localStorage.getItem(AUTH_TOKEN_KEY) || '';
export const setToken = (t) => localStorage.setItem(AUTH_TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(AUTH_TOKEN_KEY);

export class QuotaError extends Error {
  constructor(detail) {
    super('quota_exceeded');
    this.name = 'QuotaError';
    // Own accounts talk in credits; the cloud flavour in minutes. The server sends both
    // names for the same numbers, so either reader works.
    this.minutesRequired = detail?.credits_required ?? detail?.minutes_required;
    this.minutesRemaining = detail?.credits_remaining ?? detail?.minutes_remaining;
    this.creditsRequired = this.minutesRequired;
    this.creditsRemaining = this.minutesRemaining;
    this.code = detail?.error || 'quota_exceeded';   // 'quota_exceeded' | 'plan_required'
    this.feature = detail?.feature;                   // set when the plan lacks a feature
  }

  get needsPlan() { return this.code === 'plan_required'; }
}

// Fired (on window) when the server refuses the stored session token. AuthContext
// listens: it drops the signed-in state and moves the person to the sign-in page.
export const SESSION_EXPIRED_EVENT = 'viralshorts:session-expired';

// Fired (on window) for every 402, with the QuotaError as `detail`. One modal in the
// product shell listens, so each screen gets the "top up / upgrade" prompt without
// having to catch the error itself.
export const CREDITS_NEEDED_EVENT = 'viralshorts:credits-needed';

// The sign-in, sign-up and email-link endpoints answer 401/other codes about the
// credentials typed in, not about a session, so they never end one.
const SESSION_EXEMPT = /^\/api\/auth\//;

// A 401 means "this session is over" unless the server names a different reason
// (bad_credentials: a wrong current password on /api/me/password, /api/me/email,
// DELETE /api/me, which must not sign the person out).
async function isSessionExpiry(res) {
  try {
    const body = await res.clone().json();
    const code = body?.detail?.error;
    return !code || code === 'unauthenticated';
  } catch (_) {
    return true;   // not JSON (a proxy's 401 page): the token is still not accepted
  }
}

async function endSession(path, res, token) {
  if (!token || res.status !== 401 || SESSION_EXEMPT.test(path)) return;
  if (!(await isSessionExpiry(res))) return;
  // A newer sign-in may have replaced the token while this request was in flight.
  if (getToken() !== token) return;
  rememberRoute();
  clearToken();
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
}

// Drop-in fetch wrapper. Always attaches the bearer token when present.
export async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const res = await fetch(getApiUrl(path), { ...options, headers });

  await endSession(path, res, token);

  if (res.status === 402) {
    let detail = {};
    try {
      const body = await res.clone().json();
      detail = body.detail || body;
    } catch (_) { /* ignore */ }
    const err = new QuotaError(detail);
    window.dispatchEvent(new CustomEvent(CREDITS_NEEDED_EVENT, { detail: err }));
    throw err;
  }
  return res;
}

// A failed request, carrying the server's own explanation. Callers that show an
// alert should prefer `detail` — the generic "something went wrong" strings hid
// real, actionable messages (e.g. a declined card blocking checkout).
export class ApiError extends Error {
  constructor(status, detail, raw) {
    super(`${status}: ${raw}`);   // message kept verbatim for existing callers
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

// Convenience JSON helper.
export async function apiJson(path, options = {}) {
  const res = await apiFetch(path, options);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    let detail = '';
    try {
      const d = JSON.parse(text).detail;
      // FastAPI details are strings here, but validation errors arrive as objects.
      if (typeof d === 'string') detail = d;
    } catch (_) { /* not JSON — leave detail empty and fall back to the caller's copy */ }
    throw new ApiError(res.status, detail, text);
  }
  return res.json();
}
