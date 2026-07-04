# Threadly — Merchant Subscriptions & Notifications

This document describes the changes added on top of the original backend: the
merchant **subscription gate** (with an admin-controlled **free trial**) and a
fully wired **notification** system.

---

## 1. Becoming a merchant (subscription gate)

Listing a product now **requires an active merchant subscription**. The gate
lives in `require_active_merchant` (`app/api/deps.py`) and protects
`POST /api/products`. If the user has no active subscription the endpoint
returns **HTTP 402** with `{"needs_subscription": true}` so the app can route
the user to a subscribe screen.

"Active subscription" = a `Subscription` row with `status = active` and
`expires_at` in the future. It can be either a **free trial** or a **paid
monthly** plan. All of this logic is centralized in
`app/services/subscriptions.py`.

### Free trial (admin-controlled)

* Controlled by `PlatformSetting.free_trial_enabled` (a single settings row).
* When **enabled**, any user who hasn't used their trial can become a merchant
  for free for `free_trial_days` days.
* **One trial per user** (anti-abuse).
* Disabling the trial does **not** cut off people mid-trial — existing trials
  stay valid until they expire; only *new* trials are blocked.

### Paid monthly (a full month — not a trial remainder)

`start_or_extend_monthly` guarantees sound billing:

* If the user is on a **trial** and pays → the trial is replaced by a **full
  month from now** (`is_trial = False`). They never get "just the trial leftover".
* If the user already has a **paid** plan and renews early → the new month
  **stacks** on top of the current expiry, so no paid days are lost.

### Endpoints (`/api/merchant`)

| Method | Path | Purpose |
|---|---|---|
| GET  | `/merchant/status`     | Full merchant/subscription status for the UI |
| POST | `/merchant/free-trial` | Start the free trial (if enabled & unused) |
| POST | `/merchant/subscribe`  | Pay for a monthly subscription (idempotent) |
| POST | `/merchant/cancel`     | Turn off auto-renew (stays active until expiry) |

`subscribe` is **idempotent** via `idempotency_key` and records a `Transaction`
(same audit/anti-double-charge pattern as checkout). Payment processing is the
same mock as the rest of the app — replace `_charge()` in
`app/api/merchant.py` with a real Stripe call when ready.

---

## 2. Admin control of the trial (`/api/admin`)

Admins (`User.is_admin = True`) manage the platform settings at runtime — no
code change or redeploy needed.

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/settings` | Read current settings |
| PUT | `/admin/settings` | Update settings (partial) |

**Turn the free trial off:**

```bash
curl -X PUT http://localhost:8000/api/admin/settings \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"free_trial_enabled": false}'
```

You can also adjust `free_trial_days`, `monthly_price`, and
`monthly_period_days` the same way.

**Bootstrapping an admin:** put the email(s) in `ADMIN_EMAILS` in `.env`
(e.g. `ADMIN_EMAILS=["admin@threadly.app"]`). On startup those users are
granted admin automatically.

---

## 3. Notifications (now fully active)

A central service (`app/services/notifications.py`) creates every notification.
Each one is:

1. **Persisted** to the `notifications` table (visible in the list later), and
2. **Pushed live** over WebSocket if the user is connected, and
3. **Pushed via FCM** (best-effort) if the user registered a device token and
   Firebase is configured.

Notifications are best-effort: a socket/FCM failure never breaks the underlying
action (sending a message, placing an order, etc.).

### What triggers a notification

| Event | Recipient | Type |
|---|---|---|
| New chat message | the other user | `new_message` |
| Product listed | the merchant | `product_listed` |
| New order (orders & checkout) | the seller | `new_order` |
| Order placed | the buyer | `order_placed` |
| Order confirmed / shipped | the buyer | `order_status` |
| Trial started / subscribed / cancelled | the user | `subscription` |

### Real-time socket

Everything streams over **one** WebSocket (chat + notifications share it):

```
ws://<host>/api/chat/ws?token=<JWT>
```

Messages arrive as `{"type": "new_message", ...}` or
`{"type": "notification", ...}`. Multiple devices per user are supported.

### Endpoints (`/api/notifications`)

| Method | Path | Purpose |
|---|---|---|
| GET    | `/notifications`              | List + `unread_count` |
| GET    | `/notifications/unread-count` | Badge counter |
| POST   | `/notifications/{id}/read`    | Mark one read |
| POST   | `/notifications/read-all`     | Mark all read |
| DELETE | `/notifications/{id}`         | Delete one |
| POST   | `/notifications/fcm-token`    | Register a device for Push |

---

## 4. Database & migration notes

The project uses `Base.metadata.create_all`, which creates **new tables**
(`subscriptions`, `platform_settings`) automatically but does **not** add new
columns to existing tables. So on startup, `app/db/bootstrap.py` runs an
idempotent migration that:

* adds `users.is_merchant` and `users.is_admin` (`ADD COLUMN IF NOT EXISTS`),
* ensures the single `platform_settings` row exists, and
* grants admin to `ADMIN_EMAILS`.

This is safe to run on every boot. For production you may later switch to
Alembic, but this keeps the existing one-command startup working as-is.

---

## 5. New / changed files

**New**
* `app/services/subscriptions.py` — subscription/merchant logic
* `app/services/notifications.py` — notification creation + dispatch
* `app/services/realtime.py` — shared WebSocket connection manager
* `app/services/push.py` — FCM push (lazy, optional)
* `app/api/merchant.py` — merchant/subscription endpoints
* `app/api/admin.py` — platform settings endpoints
* `app/api/notifications.py` — notifications REST API
* `app/db/bootstrap.py` — startup schema/data bootstrap

**Changed**
* `app/models/__init__.py` — `Subscription`, `PlatformSetting`, enums,
  `User.is_merchant/is_admin`, `ChatThread.user1/user2/product` relationships
* `app/schemas/__init__.py` — subscription/admin/notification schemas
* `app/api/deps.py` — `require_active_merchant`, `require_admin`
* `app/api/products.py` — listing gated + "listed" notification
* `app/api/orders.py` — order notifications (new/placed/confirmed/shipped)
* `app/api/payments.py` — checkout notifications
* `app/api/chat.py` — shared manager, message notifications, self-chat guard,
  thread timestamp bump, relationship bugfix
* `app/main.py` — new routers + startup hook (loop capture + bootstrap)
* `app/core/config.py`, `.env.example` — subscription/admin/Firebase settings
