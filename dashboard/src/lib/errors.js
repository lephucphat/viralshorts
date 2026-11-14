// Turn a failed request into a sentence in the person's language.
// The server sends an English `message` next to a machine-readable `error` code;
// only the code is trusted here. An unknown code gets a generic translated line,
// never the server's English text.

// error code -> i18n key. Keys not listed here live in i18n.account.js (`err.*`)
// or, for the older sign-in strings, in i18n.studio.js (`auth.err.*`).
const CODE_KEYS = {
  bad_credentials: 'auth.err.credentials',
  email_taken: 'auth.err.taken',
  weak_password: 'auth.err.weak',
  invalid_email: 'auth.err.email',
  too_many_attempts: 'auth.err.rate',
  account_disabled: 'auth.err.disabled',
  google_denied: 'auth.err.google.denied',
  google_failed: 'auth.err.google.failed',
  google_unverified: 'auth.err.google.unverified',
  terms_required: 'err.terms_required',
  disposable_email: 'err.disposable_email',
  common_password: 'err.common_password',
  password_too_long: 'err.password_too_long',
  invalid_input: 'err.invalid_input',
  invalid_token: 'err.invalid_token',
  unauthenticated: 'err.unauthenticated',
  same_email: 'err.same_email',
  mail_off: 'err.mail_off',
  cancel_failed: 'err.cancel_failed',
  plan_required: 'err.plan_required',
  too_many_keys: 'err.too_many_keys',
  network: 'err.network',
  already_subscribed: 'billing.err.already_subscribed',
  downgrade_blocked: 'billing.err.downgrade_blocked',
  payments_off: 'billing.err.payments_off',
  checkout_failed: 'billing.err.checkout_failed',
  invalid_code: 'billing.err.invalid_code',
  already_redeemed: 'billing.err.already_redeemed',
  bad_tax_code: 'billing.err.bad_tax_code',
  billing_info_missing: 'billing.err.billing_info_missing',
};

// HTTP statuses that mean the same thing whatever the code was.
const STATUS_KEYS = {
  429: 'auth.err.rate',
  401: 'err.unauthenticated',
  503: 'err.unavailable',
  502: 'err.unavailable',
  504: 'err.unavailable',
};

// `overrides` lets one screen word a code its own way (a wrong "current
// password" is not a wrong "email or password"): { bad_credentials: 'some.key' }.
export function errorKey(err, overrides) {
  const code = err?.code;
  if (code && overrides?.[code]) return overrides[code];
  if (code && CODE_KEYS[code]) return CODE_KEYS[code];
  // fetch() itself failed: offline, DNS, CORS.
  if (!code && err instanceof TypeError) return CODE_KEYS.network;
  if (err?.status && STATUS_KEYS[err.status]) return STATUS_KEYS[err.status];
  return 'auth.err.generic';
}

export function errorMessage(t, err, overrides) {
  return t(errorKey(err, overrides));
}
