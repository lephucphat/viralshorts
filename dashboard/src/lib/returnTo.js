// Where to send the person after they sign in again: the route they were on when
// the session ended. Kept in sessionStorage (this tab only) and validated on both
// ends, because anything that reaches location.hash must be an in-app route.
const KEY = 'viralshorts_return_to';

// Routes that make no sense as a destination (or carry a one-time token).
const BLOCKED = ['#/login', '#/register', '#/auth/', '#/verify', '#/reset', '#/forgot', '#/deleted'];

export function isSafeRoute(hash) {
  if (typeof hash !== 'string' || hash.length > 300) return false;
  if (!hash.startsWith('#/')) return false;
  return !BLOCKED.some((p) => hash.startsWith(p));
}

export function rememberRoute(hash = window.location.hash) {
  if (!isSafeRoute(hash)) return;
  try { sessionStorage.setItem(KEY, hash); } catch (_) { /* storage blocked: default route */ }
}

export function clearRememberedRoute() {
  try { sessionStorage.removeItem(KEY); } catch (_) { /* ignore */ }
}

// The remembered route, once. Empty string when there is none or it is unsafe.
export function takeRememberedRoute() {
  let hash = '';
  try {
    hash = sessionStorage.getItem(KEY) || '';
    sessionStorage.removeItem(KEY);
  } catch (_) { /* ignore */ }
  return isSafeRoute(hash) ? hash : '';
}
