// A visitor who pastes a link on the landing page has no account yet. The link waits here
// (sessionStorage: it dies with the tab and never reaches a server) and the projects page
// opens the create dialog with it after sign-up or sign-in.
const KEY = 'vs_pending_source';

export function isVideoUrl(value) {
  try {
    const u = new URL(String(value || '').trim());
    return (u.protocol === 'http:' || u.protocol === 'https:') && u.hostname.includes('.');
  } catch (_) {
    return false;
  }
}

export function setPendingSource(url) {
  try { sessionStorage.setItem(KEY, url); } catch (_) { /* private mode: the visitor pastes it again */ }
}

export function takePendingSource() {
  try {
    const v = sessionStorage.getItem(KEY) || '';
    sessionStorage.removeItem(KEY);
    return isVideoUrl(v) ? v : '';
  } catch (_) {
    return '';
  }
}
