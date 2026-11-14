# Payments and credits (paid edition)

Everything here is written for this project and lives in `studio/` (MIT). It does
not use `cloud/`, whose Commercial licence forbids serving third parties.

Turn it on with `ACCOUNTS_ENABLED=1` and `STUDIO_PAID=1` (see `.env.example`).
With `STUDIO_PAID` off nothing below is active and the old free monthly-minutes
allowance applies.

## Credit model

* 1 credit = 1 minute of source video. Other actions cost more: `COSTS` in
  `studio/plans.py` (thumbnails 3, dubbing 4 per minute, AI Shorts 25 / 60).
  `GET /api/billing/plans` publishes the same table, so the UI never drifts.
* A **grant** adds credits: `plan` grants (monthly, expire at the end of the
  period) and `topup` grants (never expire). The free plan is granted lazily
  once per month.
* Spending follows reserve, then commit or release:
  `credits.reserve()` before the work, `commit(actual)` when it finishes (the
  difference to the estimate is given back), `release()` when it fails or is
  cancelled. A failed job costs nothing.
* Spend order: plan credits that expire soonest, then top-ups.
* Every write runs under `BEGIN IMMEDIATE`; two requests cannot both spend the
  last credits (there is a concurrency test).
* A reservation nobody settled is released after 6 hours (`cleanup_jobs`).
* `DAILY_AI_BUDGET_CREDITS` caps what the whole site spends on paid APIs per day.
* In paid mode a client-supplied API key is ignored, so a request header cannot
  skip the meter.

## Providers

Both providers only turn their own webhooks into the neutral operations in
`studio/payments/service.py`. The browser coming back from a checkout page never
changes an account by what it says: only a signed webhook does, or (PayOS) the server
asking PayOS itself.

| | Stripe | PayOS |
|---|---|---|
| Pays with | international cards | Vietnamese bank QR (VND) |
| Plans | recurring subscription | prepaid 30 days, buy again to continue |
| Top-up | one-off Checkout | one-off payment |
| Verification | `Stripe-Signature` HMAC-SHA256, 300 s tolerance | HMAC over sorted `key=value` fields |
| Renewal grace | 3 days | none, the period ends exactly |

Webhooks are idempotent (`payment_events`, unique per provider event) and run in
one transaction. If the user a payment refers to does not exist yet the webhook
answers 503 so the provider retries.

PayOS setup: create a payment channel at my.payos.vn, put the three `PAYOS_*` values in
`.env`, start the server on its public HTTPS address, then register the webhook with
`python -m studio.manage payos-webhook https://YOUR-DOMAIN/api/payos/webhook` (PayOS sends
a signed test notification first; the server answers 200 and grants nothing).
After paying, the page the customer returns to also asks `POST /api/billing/payos/sync`,
which checks the order with PayOS (`GET /v2/payment-requests/{orderCode}`) and applies it
through the same idempotent claim, so a late or unreachable webhook does not strand a
paying customer. Only the customer's own pending order, only for status `PAID` and the full
amount.

Routes: `GET /api/billing/plans`, `GET /api/billing/status`,
`POST /api/billing/checkout`, `POST /api/billing/portal`, `POST /api/billing/payos/sync`,
`POST /api/stripe/webhook`, `POST /api/payos/webhook`.

## Email and admin

* `studio/mailer.py` sends over plain SMTP (`SMTP_*` in `.env.example`); without
  `SMTP_HOST` nothing is sent and no verification is required.
* `studio/lifecycle.py`: verify email, forgot/reset password (single-use tokens,
  only their sha256 is stored, a reset signs out every device), payment receipts
  and a once-a-month low-credit alert. Each email is claimed in `notifications`
  first, so a webhook replay cannot send twice and a failed send is retried by the
  cleanup loop.
* With SMTP on, the free monthly credits are only granted to a verified email.
* Plan emails: a failed card renewal, a prepaid plan ending within 3 days and a plan that
  ended (`lifecycle.send_billing_notices`, from the cleanup loop and after each Stripe webhook;
  each is claimed once per period).
* Admin console `#/admin` (`studio/admin.py`), five tabs: overview (users, revenue, a 30-day
  revenue / estimated AI cost chart, margin by plan), users (search, lock, goodwill credits,
  set a plan by hand for N days, force-verify, send reset, delete the account, CSV export),
  payments (all payments with filters, subscriptions, invoice requests), system (failed
  projects, payment webhook log, filtered audit trail) and promo codes. Access is
  `ADMIN_EMAILS` **and** a verified email; everyone else gets 404. Every action is audited.
* AI cost is an **estimate**: each credit spend stores `cost_usd` from
  `plans.COST_USD_PER_CREDIT` (override with `AI_COST_RATES="dubbing=0.05,..."`); revenue is
  converted at `VND_PER_USD` (default 25000). Use it to see the margin, not to book it.
* "Mark refunded" (admin) and Stripe's `charge.refunded` / `charge.dispute.created` webhooks do
  the same thing: take back the unspent credits, end the plan the payment bought and cancel
  the Stripe subscription so a later invoice cannot revive it. Money itself is refunded in
  the Stripe or PayOS dashboard.

## Customer billing screens

* One subscription per person: a card subscription renews by itself, so a second plan is
  refused (`already_subscribed`, 409); a prepaid PayOS plan can be bought again (queues the
  next 30 days) or upgraded, not downgraded while the higher one is still paid for.
* `POST /api/billing/cancel` / `resume` (card plans, `cancel_at_period_end`),
  `GET/PUT /api/billing/info` (company, tax code, address for invoices),
  `GET /api/billing/payments/<id>` (printable receipt at `#/receipt/<id>`; the seller block
  comes from `COMPANY_NAME`, `COMPANY_TAX_CODE`, `COMPANY_ADDRESS`, `SUPPORT_EMAIL`),
  `POST /api/billing/payments/<id>/invoice` (the operator then issues the invoice by hand
  or through an e-invoice provider; there is no integration), `POST /api/billing/redeem`
  (promo code, one per person, throttled).
* A 402 from any request opens one "not enough credits / plan too low" modal
  (`CreditsModalHost`); buttons show their credit cost (`CreditNote`).

## Production and safety switches

* `APP_ENV=production` (set in `docker-compose.prod.yml`): refuses to start with a weak
  `STUDIO_SECRET` (< 32 chars or a common value), limits CORS to `FRONTEND_URL`, requires
  accepting the terms at sign-up (`REQUIRE_TERMS=0` to override).
* Sign-in, registration, password checks, promo codes and bad webhooks are throttled in SQLite
  (`rate_hits`), so a restart does not reset them. Disposable email domains are refused
  (`BLOCKED_EMAIL_DOMAINS` adds more) and Gmail dots / `+tags` count as one address.
* API keys `vsk_...` (Account page) work as Bearer tokens on the API and `/mcp`; they need a
  plan with `api_access` and cannot manage keys, export data or sign out other devices.

## Clip library (object storage)

* `output/` is a working folder (swept after about a day, lost on redeploy), so a plan's
  retention (14 / 60 days) needs a bucket. `studio/archive.py` talks to any S3-compatible
  store (R2, S3, MinIO) through boto3; set `ARCHIVE_*` in `.env.example`. Unset = off.
* When a project finishes on a plan with more than one day of retention, the clips,
  cover, captions and the small JSON files a restore needs are uploaded to
  `jobs/<job_id>/`. Never uploaded: dotfiles (the resume manifest holds a webhook
  secret), `temp_*`, the customer's raw source video, files over `ARCHIVE_MAX_FILE_MB`.
  The free plan (1 day) is not archived.
* Opening the project, or a clip URL, after the server copy is gone restores it into a
  temp folder and moves it into place only when every file arrived. Ownership comes from
  the `projects` table, not from the key; the bucket must stay private.
* An edited clip is re-uploaded. Deleting a project, or the account, deletes its
  objects. The cleanup loop deletes the objects of expired projects (a storage failure
  is retried on the next pass). The project card shows "Lưu đến <ngày>".
* Admin overview shows how many projects and bytes are archived.
* Limits: no lifecycle rule is set on the bucket (the sweep is the only deleter, so add a
  bucket rule as a safety net); a plan downgrade does not shorten files already stored.

## Library and workspace features (phase 10)

* **Source preview** (`studio/preview.py`, `GET /api/source/preview?url=`): reads title,
  channel, cover and length with yt-dlp (no download), so the create dialog can show
  "about N credits" before anything is spent. Public URLs only (`assert_public_url`),
  40 lookups per 10 minutes per person, results cached 10 minutes, errors are generic.
* **Recipes** (`studio/recipes.py`, `/api/recipes`): a person's saved create-dialog
  settings. Only a fixed list of keys is stored (genre, language, clip length, keywords,
  layout, kit, captions...), up to 20 per person, names unique ignoring case.
* **Notification bell** (`studio/inbox.py`, `/api/inbox`): "clips ready", "project failed"
  and "running low on credits" (once per month). Written when a job finishes
  (`_studio_job_finished`); the bell polls every 60 s while the tab is visible. Kept: the
  newest 100 per person. This is separate from `notifications`, which only de-duplicates
  emails.
* Collections and favorites (migration 11), recipes (12) and the inbox (13) are
  append-only migrations in `studio/db.py`.

## Known gaps (be honest about them when presenting)

* The bell has been tested with seeded rows and unit tests, not yet with a real project
  that finishes. Source preview was only tried on YouTube links.
* Per-criterion virality scores (hook, flow, value, trend) are shown only if the backend
  supplies them; otherwise the card shows the single score it has.

* **PayOS is checked against its documentation, not against the live service.** The
  webhook signature code reproduces the sample signature in PayOS's own docs, the request
  signature follows the documented field order, and the description is kept within the
  9-character limit. Still unproven without keys: the create-link call, the webhook
  delivery, the `PAID` status string (the docs only show `PENDING` and `CANCELLED`) and how
  PayOS appends its query to the return URL. Run one sandbox payment before trusting it.
* Stripe is meant for test mode here. Whether a Vietnam-based business can take
  live Stripe payments has to be confirmed with Stripe.
* A partial Stripe refund is ignored (only a full refund reverses the plan); PayOS refunds
  are marked by an admin by hand. Credits already spent cannot be taken back (`unrecovered`).
* Receipts are not VAT invoices. Vietnamese e-invoices (MISA, VNPT...) need a contract with a
  provider and are not integrated; the console only lists who asked for one.
* Plan retention is enforced for archived clips (bucket) but the local working folder is
  still swept after about a day, so without `ARCHIVE_*` set a paid plan keeps nothing longer.
* Email is plain SMTP with a small HTML template; no bounce handling.
* Yearly plans are not supported (the `yearly_discount_months` field is unused).
* Retrying a failed AI Short charges again.
* For a URL job the cost is unknown up front: 10 credits must be available to
  start, then the real length is settled at the end (capped by the balance).
* Prices and costs in `studio/plans.py` are placeholders. Set them from your real
  API costs plus a margin.
* One SQLite file (WAL) fits a single server. Move to Postgres only to scale out.

## Testing

```bash
python -m pytest tests/test_studio_credits.py tests/test_studio_paid_integration.py tests/test_studio_payments.py
```

Stripe end to end in test mode: set the two `STRIPE_*` keys, run
`stripe listen --forward-to localhost:8000/api/stripe/webhook`, buy a plan with
card `4242 4242 4242 4242`.
