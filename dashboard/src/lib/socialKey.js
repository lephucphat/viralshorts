// The Upload-Post key and profile, shared with the project workspace (App.jsx).
//
// App.jsx keeps them in localStorage under the names below, with a light XOR obfuscation (not
// real encryption: anything in the browser is readable by the person using it, the point is only
// to keep the key out of a casual look at DevTools). The calendar page needs the same key to send
// posts, so it reads and writes the same two entries in the same format. Change both together.

const SECRET_KEY = import.meta.env.VITE_ENCRYPTION_KEY || 'ViralShorts-Static-Salt-Change-Me';
const PREFIX = 'ENC:';
const KEY_ENTRY = 'uploadPostKey_v3';
const USER_ENTRY = 'uploadUserId';

const xor = (text) =>
  text.split('').map((c, i) => String.fromCharCode(c.charCodeAt(0) ^ SECRET_KEY.charCodeAt(i % SECRET_KEY.length))).join('');

export function getUploadPostKey() {
  try {
    const stored = localStorage.getItem(KEY_ENTRY);
    if (!stored) return '';
    if (!stored.startsWith(PREFIX)) return stored;       // an older plain-text entry
    return xor(atob(stored.slice(PREFIX.length)));
  } catch (_) {
    return '';
  }
}

export function setUploadPostKey(key) {
  try {
    if (key) localStorage.setItem(KEY_ENTRY, PREFIX + btoa(xor(key)));
    else localStorage.removeItem(KEY_ENTRY);
  } catch (_) { /* storage blocked: the key just will not be remembered */ }
}

export function getUploadUserId() {
  try { return localStorage.getItem(USER_ENTRY) || ''; } catch (_) { return ''; }
}

export function setUploadUserId(id) {
  try {
    if (id) localStorage.setItem(USER_ENTRY, id);
    else localStorage.removeItem(USER_ENTRY);
  } catch (_) { /* see above */ }
}
