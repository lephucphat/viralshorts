// Client for the own-accounts API (studio/): projects, brand kits, usage.
// Everything goes through apiFetch, so the bearer token is attached once.
import { apiFetch, QuotaError } from './api';

export class StudioError extends Error {
  constructor(status, code, message) {
    super(message || code || `http_${status}`);
    this.name = 'StudioError';
    this.status = status;
    this.code = code || `http_${status}`;
  }
}

async function toError(res) {
  let code = '';
  let message = '';
  try {
    const body = await res.json();
    const d = body?.detail;
    if (d && typeof d === 'object') { code = d.error || ''; message = d.message || ''; }
    else if (typeof d === 'string') message = d;
  } catch (_) { /* not JSON */ }
  return new StudioError(res.status, code, message);
}

export async function studioJson(path, { method = 'GET', body, form } = {}) {
  const init = { method };
  if (form) init.body = form;
  else if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }
  const res = await apiFetch(path, init);
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return {};   // e.g. a DELETE with nothing to say
  return res.json();
}

export const inboxApi = {
  list: () => studioJson('/api/inbox'),
  read: (id) => studioJson('/api/inbox/read', { method: 'POST', body: id == null ? {} : { id } }),
};

export const recipesApi = {
  list: () => studioJson('/api/recipes'),
  create: (name, settings) => studioJson('/api/recipes', { method: 'POST', body: { name, settings } }),
  remove: (id) => studioJson(`/api/recipes/${id}`, { method: 'DELETE' }),
};

export const draftsApi = {
  list: (kind = 'thumbnails') => studioJson(`/api/drafts?${new URLSearchParams({ kind })}`),
  get: (id) => studioJson(`/api/drafts/${encodeURIComponent(id)}`),
  save: (id, data, kind = 'thumbnails') => studioJson(`/api/drafts/${encodeURIComponent(id)}`, { method: 'PUT', body: { kind, data } }),
  remove: (id) => studioJson(`/api/drafts/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};

export const sourceApi = {
  preview: (url) => studioJson(`/api/source/preview?${new URLSearchParams({ url })}`),
};

export const projectsApi = {
  list: ({ q = '', status = '', sort = 'newest', limit = 60, offset = 0, favorite = false, collection = null } = {}) => {
    const params = new URLSearchParams({ q, status, sort, limit, offset });
    if (favorite) params.set('favorite', 'true');
    if (collection != null) params.set('collection', collection);
    return studioJson(`/api/projects?${params}`);
  },
  favorite: (jobId, favorite) => studioJson(`/api/projects/${encodeURIComponent(jobId)}/favorite`, { method: 'PUT', body: { favorite } }),
  collectionIds: (jobId) => studioJson(`/api/projects/${encodeURIComponent(jobId)}/collections`),
  get: (jobId) => studioJson(`/api/projects/${encodeURIComponent(jobId)}`),
  rename: (jobId, title) => studioJson(`/api/projects/${encodeURIComponent(jobId)}`, { method: 'PATCH', body: { title } }),
  remove: (jobId) => studioJson(`/api/projects/${encodeURIComponent(jobId)}`, { method: 'DELETE' }),
  cancel: (jobId) => studioJson(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' }),
};

export const collectionsApi = {
  list: () => studioJson('/api/collections'),
  create: (name) => studioJson('/api/collections', { method: 'POST', body: { name } }),
  rename: (id, name) => studioJson(`/api/collections/${id}`, { method: 'PATCH', body: { name } }),
  remove: (id) => studioJson(`/api/collections/${id}`, { method: 'DELETE' }),
  add: (id, jobId) => studioJson(`/api/collections/${id}/projects`, { method: 'POST', body: { job_id: jobId } }),
  take: (id, jobId) => studioJson(`/api/collections/${id}/projects/${encodeURIComponent(jobId)}`, { method: 'DELETE' }),
};

export const kitsApi = {
  list: () => studioJson('/api/brand-kits'),
  create: (fields) => studioJson('/api/brand-kits', { method: 'POST', body: fields }),
  update: (id, fields) => studioJson(`/api/brand-kits/${id}`, { method: 'PATCH', body: fields }),
  remove: (id) => studioJson(`/api/brand-kits/${id}`, { method: 'DELETE' }),
  uploadLogo: (id, file) => {
    const form = new FormData();
    form.append('file', file);
    return studioJson(`/api/brand-kits/${id}/logo`, { method: 'POST', form });
  },
  removeLogo: (id) => studioJson(`/api/brand-kits/${id}/logo`, { method: 'DELETE' }),
};

export const accountApi = {
  update: (fields) => studioJson('/api/me', { method: 'PATCH', body: fields }),
  changePassword: (current, next) =>
    studioJson('/api/me/password', { method: 'POST', body: { current, new: next } }),
  remove: (password) => studioJson('/api/me', { method: 'DELETE', body: { password } }),
  // Revokes every device and returns { token, user }: the caller stores the new token.
  logoutAll: () => studioJson('/api/me/logout-all', { method: 'POST' }),
  // For a Google-only account `password` is the account's current email, typed in.
  changeEmail: (email, password) =>
    studioJson('/api/me/email', { method: 'POST', body: { email, password } }),
  // The endpoint needs the Authorization header, so it cannot be a plain link:
  // fetch it with the token and hand the caller a Blob to save.
  exportData: async () => {
    const res = await apiFetch('/api/me/export');
    if (!res.ok) throw await toError(res);
    return res.blob();
  },
};

// API keys (`vsk_...`) for scripts, AI agents and the /mcp endpoint. The full key is
// returned once, by create.
export const keysApi = {
  list: () => studioJson('/api/keys'),
  create: (name) => studioJson('/api/keys', { method: 'POST', body: { name } }),
  revoke: (id) => studioJson(`/api/keys/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};

// Plans, credit packs and payment. Checkout and the portal return a URL on the payment
// provider's own page: the browser is sent there, and the account is only changed later by
// the provider's signed webhook (never by the browser coming back).
export const billingApi = {
  plans: () => studioJson('/api/billing/plans'),
  status: () => studioJson('/api/billing/status'),
  checkout: ({ kind, item, provider }) =>
    studioJson('/api/billing/checkout', { method: 'POST', body: { kind, item, provider } }),
  portal: () => studioJson('/api/billing/portal', { method: 'POST' }),
  syncPayos: (order) => studioJson('/api/billing/payos/sync', { method: 'POST', body: { order } }),
  cancel: () => studioJson('/api/billing/cancel', { method: 'POST' }),
  resume: () => studioJson('/api/billing/resume', { method: 'POST' }),
  info: () => studioJson('/api/billing/info'),
  saveInfo: (info) => studioJson('/api/billing/info', { method: 'PUT', body: info }),
  receipt: (id) => studioJson(`/api/billing/payments/${encodeURIComponent(id)}`),
  requestInvoice: (id) => studioJson(`/api/billing/payments/${encodeURIComponent(id)}/invoice`, { method: 'POST' }),
  redeem: (code) => studioJson('/api/billing/redeem', { method: 'POST', body: { code } }),
};

// Email-driven account flows. Forgot always answers ok (the server never says who has an
// account); the others fail with a StudioError whose `code` the page maps to a sentence.
export const recoveryApi = {
  forgot: (email) => studioJson('/api/auth/forgot', { method: 'POST', body: { email } }),
  reset: (token, password) => studioJson('/api/auth/reset', { method: 'POST', body: { token, password } }),
  verify: (token) => studioJson('/api/auth/verify', { method: 'POST', body: { token } }),
  // Signed in: { sent: true } or { sent: false, reason: 'already_verified' | 'mail_off' }.
  resend: () => studioJson('/api/me/verify/resend', { method: 'POST' }),
  // No session needed (an expired link); always answers ok.
  resendFor: (email) => studioJson('/api/auth/verify/resend', { method: 'POST', body: { email } }),
};

// The operator console. Every route answers 404 to anyone who is not an admin.
export const adminApi = {
  overview: () => studioJson('/api/admin/overview'),
  users: ({ q = '', limit = 50, offset = 0 } = {}) =>
    studioJson(`/api/admin/users?${new URLSearchParams({ q, limit, offset })}`),
  user: (id) => studioJson(`/api/admin/users/${id}`),
  disable: (id) => studioJson(`/api/admin/users/${id}/disable`, { method: 'POST' }),
  enable: (id) => studioJson(`/api/admin/users/${id}/enable`, { method: 'POST' }),
  grant: (id, credits, note) =>
    studioJson(`/api/admin/users/${id}/grant`, { method: 'POST', body: { credits, note } }),
  refund: (paymentId, note) =>
    studioJson(`/api/admin/payments/${paymentId}/refund`, { method: 'POST', body: { note } }),
  audit: ({ limit = 100, offset = 0, action = '' } = {}) =>
    studioJson(`/api/admin/audit?${new URLSearchParams({ limit, offset, action })}`),
  series: (days = 30) => studioJson(`/api/admin/series?days=${days}`),
  payments: ({ status = '', provider = '', q = '', limit = 50, offset = 0 } = {}) =>
    studioJson(`/api/admin/payments?${new URLSearchParams({ status, provider, q, limit, offset })}`),
  subscriptions: ({ status = '', limit = 50, offset = 0 } = {}) =>
    studioJson(`/api/admin/subscriptions?${new URLSearchParams({ status, limit, offset })}`),
  failedProjects: () => studioJson('/api/admin/failed-projects'),
  webhookEvents: () => studioJson('/api/admin/webhook-events'),
  invoiceRequests: () => studioJson('/api/admin/invoice-requests'),
  setPlan: (id, plan, days, note) =>
    studioJson(`/api/admin/users/${id}/plan`, { method: 'POST', body: { plan, days, note } }),
  verifyEmail: (id) => studioJson(`/api/admin/users/${id}/verify-email`, { method: 'POST' }),
  sendReset: (id) => studioJson(`/api/admin/users/${id}/send-reset`, { method: 'POST' }),
  deleteUser: (id) => studioJson(`/api/admin/users/${id}`, { method: 'DELETE' }),
  promos: () => studioJson('/api/admin/promos'),
  createPromo: (body) => studioJson('/api/admin/promos', { method: 'POST', body }),
  setPromoActive: (code, active) =>
    studioJson(`/api/admin/promos/${encodeURIComponent(code)}/active`, { method: 'POST', body: { active } }),
  // CSV needs the bearer header, so fetch it and hand the browser a blob to save.
  exportCsv: async (kind) => {
    const res = await apiFetch(`/api/admin/export/${kind}`);
    if (!res.ok) throw new Error(`${res.status}`);
    return res.blob();
  },
};

// Start a project. `source` is { kind: 'url', url } or { kind: 'file', file };
// `options` is the already-cleaned set of fields to send (empty values dropped).
// Returns the server's JSON: { job_id } or { needs_confirmation, quality_check }.
export async function createProject(source, options, { forceLowQuality = false } = {}) {
  const clean = Object.fromEntries(
    Object.entries(options).filter(([, v]) => v !== '' && v != null));
  let res;
  if (source.kind === 'url') {
    res = await apiFetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: source.url, acknowledged: true, force_low_quality: forceLowQuality, ...clean,
      }),
    });
  } else {
    const form = new FormData();
    form.append('file', source.file);
    form.append('acknowledged', 'true');
    for (const [k, v] of Object.entries(clean)) form.append(k, String(v));
    res = await apiFetch('/api/process', { method: 'POST', body: form });
  }
  if (!res.ok) throw await toError(res);
  return res.json();
}

export { QuotaError };

// "3 phút trước", "2 days ago": coarse on purpose, a library card needs no seconds.
export function timeAgo(epochSeconds, lang) {
  const diff = Math.max(0, Date.now() / 1000 - epochSeconds);
  const units = [['year', 31536000], ['month', 2592000], ['day', 86400], ['hour', 3600], ['minute', 60]];
  const rtf = new Intl.RelativeTimeFormat(lang === 'vi' ? 'vi' : 'en', { numeric: 'auto' });
  for (const [unit, secs] of units) {
    if (diff >= secs) return rtf.format(-Math.floor(diff / secs), unit);
  }
  return rtf.format(0, 'second');
}

export function formatDuration(seconds) {
  const s = Math.round(Number(seconds) || 0);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`;
}

// First-run checklist (studio/onboarding.py). Only "pricing" and "social" are reported by the
// client; the other steps are derived on the server from real data.
export const onboardingApi = {
  get: () => studioJson('/api/me/onboarding'),
  report: (step) => studioJson(`/api/me/onboarding/${encodeURIComponent(step)}`, { method: 'POST' }),
  dismiss: () => studioJson('/api/me/onboarding/dismiss', { method: 'POST' }),
};

// Posting calendar (studio/schedule.py). Times are UTC epoch seconds. The real queue lives at
// Upload-Post under the person's own key; the dashboard reports each outcome with `setStatus`.
export const calendarApi = {
  list: (start, end) => studioJson(`/api/calendar?start=${Math.floor(start)}&end=${Math.floor(end)}`),
  create: (post) => studioJson('/api/calendar', { method: 'POST', body: post }),
  update: (id, fields) => studioJson(`/api/calendar/${id}`, { method: 'PATCH', body: fields }),
  setStatus: (id, status, { vendorJobId, error } = {}) =>
    studioJson(`/api/calendar/${id}/status`, {
      method: 'POST', body: { status, vendor_job_id: vendorJobId, error: error || '' } }),
  remove: (id) => studioJson(`/api/calendar/${id}`, { method: 'DELETE' }),
};

// Friend referrals (studio/referral.py).
export const referralApi = {
  get: () => studioJson('/api/referral'),
  attach: (code) => studioJson('/api/referral/attach', { method: 'POST', body: { code } }),
};

// Public: where support mail goes (the operator's SUPPORT_EMAIL, blank until it is set).
export const helpApi = {
  contact: () => studioJson('/api/help/contact'),
};
