# E0b — Orsyn admin: model providers, keys, routing and spend

Status: draft, waiting for founder OK. Author: architect. Date: 2026-10-05. Story key is **provisional** (see Q1).

Inputs read: `CLAUDE.md`, `KICKOFF.md`, `.claude/agents/*`, `docs/plans/E0-repo-ci.md`. **Missing:** `docs/build-plan.md`, `docs/screens.md` and `docs/architecture.md` do not exist yet, and neither does any code. E0 creates stubs for them. This plan builds on E0's design (§3.2 settings, §3.3 gateway interface) and changes nothing in it.

AWS facts were checked on 2026-10-05 against the Bedrock user guide: model access, inference profiles, inference-profile IAM prerequisites, and the model cards for Sonnet 5.5, Sonnet 4.6, Opus 5.5 and Haiku 4.5. infra re-checks them when the account exists, because they change often.

---

## 1. Goal

Give Orsyn staff, and nobody else, an admin area for model and third-party providers. In it they can see each provider's status, set or rotate keys that are written once and never shown again, and test a provider through the gateway. They can also see the routing that is in force and set spend caps that the gateway enforces. Costs are read from the gateway's own log. Every admin action is audited.

> Done when (**proposed**: `docs/build-plan.md` does not exist, so the founder must confirm this text, Q1):
> (a) only an active Orsyn admin can open the admin area, and every admin action is in the event log;
> (b) an owner can set or rotate a provider key; it is stored only in AWS Secrets Manager and afterwards only its last 4 characters and rotated-at time are ever shown;
> (c) "Test connection" makes one call through the gateway and the call's cost is logged;
> (d) the gateway picks up a rotated key without a redeploy and refuses to call a provider that is missing, disabled or over its spend cap;
> (e) the admin can see month-to-date spend by feature, customer and model against the caps.

### 1.1 Who is who

| | Orsyn admin (staff) | Customer org user |
| --- | --- | --- |
| Who | Orsyn employees: Veeru, Nithish, later ops staff | Buyers and suppliers |
| Identity | Company IdP account (Google Workspace assumed, Q4) with enforced 2-step verification | Customer login (a later story; not designed here) |
| Where | `admin.<domain>` only | the app host |
| Authorisation | Row in `staff_admins` with `role ∈ {owner, viewer}` and `active = true` | Org membership (later story) |
| Can do here | viewer: read everything in admin. owner: also set keys, test, enable or disable, edit caps | Nothing. Admin routes never accept a customer credential |

- The two identity systems never mix.
- A staff member who also needs a customer test account uses a separate identity.
- **Not building:** impersonating customers, staff editing any customer data, or customer-facing usage pages.

### 1.2 How admin access is gated (defence in depth, all cheap)

1. **ALB authentication on the admin host.** The ALB listener rule for `admin.<domain>` uses `authenticate-oidc` against the company IdP. Unauthenticated requests never reach a container. The session timeout is 8 hours.
2. **MFA** is enforced at the IdP (Workspace 2-step verification is mandatory for the Orsyn domain). The ALB rule also checks the `hd` claim (hosted domain) so only Orsyn-domain accounts get through.
3. **The api verifies the ALB-signed JWT itself** (`x-amzn-oidc-data`):
   - ES256 signature, using the regional ALB public key looked up by `kid`;
   - `signer` equals our ALB ARN;
   - `exp` has not passed;
   - email domain matches.

   It then looks the email up in `staff_admins`. Customer routes never read this header. Admin routes read nothing else.
4. **Host check:** admin routers only answer when `Host` equals `ORSYN_ADMIN_HOST`, and the customer host returns 404 for `/admin/*`, both in the api and in Next middleware.
5. **IP allow-list: optional.** An ALB `source-ip` condition costs nothing, but founders on mobile or home connections would lock themselves out. It is off by default and switched on if a static office or VPN IP exists (Q5).
6. **CSRF:** mutations need the `X-Orsyn-Admin: 1` header, `Content-Type: application/json`, and an `Origin` equal to the admin host.
7. **Not in OpenAPI:** admin routes are registered with `include_in_schema=False`.
8. **Local dev only:** with `ORSYN_ADMIN_AUTH=dev_header`, the `X-Orsyn-Dev-Admin: <email>` header is accepted. A settings validator **refuses to start** if this mode is set while `ORSYN_ENV` is `dev` or `prod`.

### 1.3 Where secrets live

| Provider | Auth | Where the credential lives |
| --- | --- | --- |
| Claude via **AWS Bedrock** | **ECS task IAM role.** No API key at all; boto3 default credential chain | Nothing to store. Bedrock long-term API keys are **not used**; infra denies their use (Q11) |
| Claude via **Anthropic API** (direct) | API key | Slot `orsyn/<env>/providers/anthropic`. **Adapter deferred** (Q7); the slot shows "Missing / not used" |
| **Sarvam** | API key | `orsyn/<env>/providers/sarvam` |
| WhatsApp Cloud API, GST lookup, later others | API key / token | `orsyn/<env>/providers/<name>` slots exist now with status "Missing". Adapters and tests come with their own stories |

Rules:

- **Storage.** Secrets live only in AWS Secrets Manager, never in Postgres, the repo, env files committed to git, logs, events, error messages or API responses.
- **Secret format.** Each secret is JSON `{"api_key": "..."}`, encrypted with the default `aws/secretsmanager` KMS key (no customer-managed key, so $0).
- **Placeholders.** infra pre-creates each secret as a placeholder. The api role may `GetSecretValue` and `PutSecretValue` on exactly those ARNs. It may **not** create, delete or list secrets.
- **Write path.** The browser sends the key once over HTTPS in a password field. The api forwards it with `PutSecretValue` and keeps only `last4`, the Secrets Manager `VersionId` and `rotated_at` in Postgres. The key is never read back for display.
- **Out-of-band rotation.** If Veeru rotates a key from the CLI instead, the version will not match the recorded one. The screen then says "Changed outside admin; last 4 unknown" and still works.

### 1.4 What is deliberately not built

- **Runtime editing of model routing.** Routing stays in code and changes by PR, so evals run and Veeru confirms by merging (§5).
- A direct Anthropic adapter and a Claude transport failover switch (Q7).
- Test connection for WhatsApp and GST.
- INR conversion of costs (Q9).
- Charts.
- Customer impersonation.
- A separate admin service or Next.js app.
- Per-call prompt or response viewing. Bedrock model-invocation logging stays **off**, because it would store prompts with personal data.
- Reconciliation against the AWS bill (manual monthly check, §9).
- Automatic key rotation (keys come from vendors).

---

## 2. Ontology impact

**Dependency:** this story needs a DB baseline that nobody has built yet:

- Alembic set up;
- Postgres in CI;
- an `orgs` table with a **platform org** row for Orsyn itself;
- the append-only `events` table.

E0 leaves this to "the first story that adds a table". Recommended: a tiny **E0c DB baseline** story ahead of E0b and M1 (Q2). E0b needs only `orgs(id, kind ∈ {platform, buyer, supplier}, name, created_at, created_by)` and the `events` shape in §4.

All four new tables below have `id` (uuid), `org_id`, `created_at` (timestamptz, UTC) and `created_by` (actor string `person:<uuid>`, `agent:<name>` or `system:<component>`).

- **Config tables** belong to the **platform org**. Their `org_id` is the platform org, so no customer-scoped query can reach them.
- **`model_calls`** carries the customer org that triggered the call.

There are no documents or PO lines in this story, so the document-line → PO-line link does not apply.

### 2.1 `staff_admins`
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid FK orgs | platform org |
| `email` | citext unique | IdP email; the only personal data here |
| `role` | text check in (`owner`,`viewer`) | |
| `active` | bool default true | deactivate, never delete |
| `created_at`, `created_by`, `updated_at`, `updated_by` | | |

- **Bootstrap:** the first owner is created by a one-off CLI, `uv run python -m app.admin.bootstrap --email … --role owner`, run as an ECS one-off task by Veeru. It writes an event with actor `system:bootstrap`. After that, owners manage staff through the CLI only (a staff UI is deferred).
- No seed emails go into migrations.

### 2.2 `provider_credentials` (one row per provider per environment)
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | platform org |
| `provider` | text unique | `bedrock`, `anthropic`, `sarvam`, `whatsapp_cloud`, `gst_lookup` |
| `kind` | text | `model` or `tool` |
| `auth_method` | text | `iam_role` or `api_key` |
| `secret_name` | text null | e.g. `orsyn/dev/providers/sarvam`; null for `iam_role`. A name, never a value |
| `secret_version_id` | text null | Secrets Manager VersionId recorded at our last write |
| `key_last4` | char(4) null | |
| `rotated_at`, `rotated_by` | timestamptz, text | |
| `enabled` | bool default true | admin kill switch; the gateway refuses when false |
| `disabled_reason` | text null | |
| `last_test_at`, `last_test_ok`, `last_test_error_code` | | Code is an enum string (`auth_failed`, `access_denied`, `throttled`, `timeout`, `unavailable`, `bad_response`); **no raw vendor message** |
| `last_test_model_call_id` | uuid FK model_calls null | links the test to its cost row |
| `created_at`, `created_by`, `updated_at`, `updated_by` | | |

Rows are seeded by the migration (no secret values).

**Status is computed and never stored:**
- `Disabled` if `enabled = false`.
- `Missing` if `auth_method = api_key` and there is no version.
- `Failing` if the last test failed, or if at least 3 calls in the last 15 minutes have an error rate of 50% or more.
- `Configured` otherwise.

### 2.3 `spend_caps`
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | platform org (owner of the rule) |
| `target_org_id` | uuid FK orgs null | null = all customers |
| `feature` | text null | null = all features |
| `period` | text check = `month_ist` | calendar month in Asia/Kolkata; boundaries computed in code, stored UTC |
| `limit_amount` | numeric(12,4) | `Decimal` |
| `currency` | char(3) check = `USD` | providers bill in USD |
| `alert_pct` | smallint default 80 | soft alert threshold |
| `active` | bool | soft delete |
| `created_at`, `created_by`, `updated_at`, `updated_by` | | |

- There is a unique partial index on (`coalesce(target_org_id)`, `coalesce(feature)`) where `active`.
- The migration seeds a **global fuse**: `target_org_id` null, `feature` null, with a limit the founder sets (Q8).
- **A feature kill switch is just a cap of 0**, so no extra table is needed.

### 2.4 `model_calls` (the gateway's cost log, append-only)
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | customer org that caused the call; platform org for admin tests and evals |
| `feature` | text | e.g. `rfq_from_drawing`, `admin_provider_test` |
| `provider`, `model_id` | text | `model_id` = the exact inference profile ID sent |
| `prompt_id`, `prompt_version` | text | |
| `input_tokens`, `output_tokens` | int | |
| `cost_amount` | numeric(14,6) | computed in code from `prices.py` |
| `currency` | char(3) | `USD` |
| `price_ref` | text | price row id + checked date (traceability) |
| `latency_ms` | int | |
| `status` | text | `ok`, `error`, `blocked_cap`, `blocked_disabled`, `unavailable` |
| `error_code` | text null | same enum as §2.2 |
| `request_id` | text | |
| `created_at`, `created_by` | | `created_by` = `agent:<name>` or `person:<id>` |

- **Indexes:** (`org_id`, `created_at`), (`feature`, `created_at`), (`provider`, `created_at`).
- **Append-only:** a trigger raises an error on UPDATE or DELETE.
- **No prompt, response, file name or contact text, ever.**
- The E0 `orsyn.ai.cost` log line stays; this table is in addition to it.

---

## 3. API

**Common rules for every endpoint:**
- Base path `/admin/v1`, served only on the admin host.
- Admin dependency: ALB JWT plus an active `staff_admins` row.
- Responses are JSON. Errors use `{"error": {"code", "message"}}`.
- Times are ISO-8601 UTC; the UI shows IST.
- Money is a string decimal plus `currency`.

**Status codes:**
- 401: no or invalid ALB JWT.
- 403: not in `staff_admins`, inactive, or `viewer` on an owner action (writes `admin.access_denied`).
- 404: wrong host.

| Method and path | Who | Request | Response | Errors |
| --- | --- | --- | --- | --- |
| `GET /me` | viewer, owner | | `{email, role, env}` | |
| `GET /providers` | viewer, owner | | `[{provider, kind, auth_method, status, key_last4, rotated_at, changed_outside_admin, enabled, last_test: {at, ok, error_code, cost_amount, currency}}]` | |
| `GET /providers/{provider}` | viewer, owner | | the list item plus `region`, `models: [{feature, model_id}]` (from routing), `recent_events[≤10]` | 404 unknown |
| `PUT /providers/{provider}/key` | **owner** | `{api_key: SecretStr (16–512 chars, no whitespace), confirm_provider: str}` | `{key_last4, rotated_at}` | 400 `iam_role_provider` (Bedrock has no key); 409 `confirm_mismatch`; 422 `invalid_key_format`; 502 `secret_store_error` (generic; no AWS message passed through) |
| `POST /providers/{provider}/test` | **owner** | `{}` | `{ok, latency_ms, model_id, cost_amount, currency, error_code, model_call_id}` | 409 `missing`/`disabled`; 429 `rate_limited` (1 per provider per 30 s); 501 `test_not_supported` (whatsapp_cloud, gst_lookup, anthropic in this story) |
| `POST /providers/{provider}/disable` | **owner** | `{reason: str 3–200}` | provider item | |
| `POST /providers/{provider}/enable` | **owner** | `{}` | provider item | |
| `GET /routing` | viewer, owner | | `{git_sha, rows: [{feature, provider, model_id, fallback_model_id, fallback_rule, max_tokens}]}` read from code | |
| `GET /spend-caps` | viewer, owner | | `[{id, target_org: {id,name}\|null, feature, limit_amount, currency, alert_pct, mtd_amount, mtd_pct, state ∈ {ok, alerting, blocked}}]` | |
| `POST /spend-caps` | **owner** | `{target_org_id?, feature?, limit_amount, currency:"USD", alert_pct}` | cap | 409 duplicate scope; 422 negative amount or `alert_pct` outside 1–100 |
| `PATCH /spend-caps/{id}` | **owner** | `{limit_amount?, alert_pct?, active?}` | cap | 404 |
| `GET /costs/summary?month=YYYY-MM` | viewer, owner | | `{month, tz:"Asia/Kolkata", total, by_feature[], by_org[{org_id, org_name, amount}], by_model[], by_provider[], calls, errors}` (all amounts summed in SQL as numeric, returned as strings) | 422 bad month |
| `GET /costs/calls?month&org_id&feature&status&cursor` | viewer, owner | | `{items: [model_calls row minus request internals], next_cursor}`, 50 per page | |
| `GET /audit?type_prefix&cursor` | viewer, owner | | events written by admin or gateway sources, 50 per page | |

**Handling the key safely:**
- `api_key` is a Pydantic `SecretStr`.
- Request-body logging is skipped for `PUT …/key`.
- On success, the handler invalidates this task's secret cache entry. Other tasks pick the new key up within the cache TTL (§5.3).
- The handler then writes `provider_credential.rotated` (or `.set` the first time).
- The UI suggests "Test connection" next. There is no automatic test, so there is no hidden spend.

---

## 4. Events

The event row shape (from E0c) is:

- `id`, `org_id`, `created_at`, `created_by` (actor);
- `source ∈ {admin_ui, admin_cli, gateway, job}`;
- `type`, `subject_type`, `subject_id`;
- `payload` jsonb, `request_id`, `client_ip` (admin only).

Events are append-only. **Payloads never contain key material, prompts or contact data.** A test enforces this (§8).

| Type | Actor | Source | Payload |
| --- | --- | --- | --- |
| `admin.access_denied` | `person:<email hash>` or `anonymous` | admin_ui | `{reason, path}` |
| `admin.viewed` | person | admin_ui | `{path}`, for cross-org reads only (`/costs/*`, `/spend-caps`, `/audit`); at most one per path per person per 10 minutes |
| `staff_admin.created` / `.role_changed` / `.deactivated` | person or `system:bootstrap` | admin_cli | `{email, role}` |
| `provider_credential.set` / `.rotated` | person | admin_ui | `{provider, key_last4, secret_version_id}` |
| `provider_credential.changed_outside_admin` | `system:gateway` | gateway | `{provider, secret_version_id}`, once per new version |
| `provider.test_run` | person | admin_ui | `{provider, ok, error_code, model_call_id, cost_amount, currency}` |
| `provider.disabled` / `.enabled` | person | admin_ui | `{provider, reason}` |
| `spend_cap.created` / `.updated` / `.deactivated` | person | admin_ui | `{before, after}` |
| `spend_cap.alert_crossed` | `system:gateway` | gateway | `{cap_id, mtd_amount, limit_amount, pct}`, once per cap per month per threshold |
| `spend_cap.blocked` | `system:gateway` | gateway | `{cap_id, feature, org_id}`, first block per cap per IST day |
| `provider.unavailable` | `system:gateway` | gateway | `{provider, error_code}`, first per provider per 15 minutes |

Alerts reach people without any app email code:

- The gateway also emits the structured log lines `orsyn.ai.spend_alert` and `orsyn.ai.provider_unavailable`.
- infra adds CloudWatch metric filters on them, alarms and an SNS email topic to the founders.

---

## 5. AI agents

**No new agent and no agent change.** This story changes the gateway (the infrastructure for agents) and adds one fixed probe.

### 5.1 Connectivity probe (not an agent)
- **Prompt file:** `services/api/app/ai/prompts/provider_test.md`, id `provider_test`, **version 1**, with a changelog.
- **Content:** "Reply with the single word OK." with `max_tokens: 5`. It contains no customer data.
- **Feature name:** `admin_provider_test`. `org_id` is the platform org. `created_by` is `person:<staff id>`.
- **Output:** text only. `ok` is true when the call succeeds and returns a non-empty response. No confidence field, because nothing is extracted or proposed.
- **Approval point:** the owner pressing "Test connection" *is* the human action. Nothing leaves the platform except the probe to the vendor.
- **Bedrock test:** uses the cheapest routed Claude model (the Haiku-role model).
- **Sarvam test:** uses its cheapest text endpoint. ai-engineer picks it from Sarvam's docs and records the endpoint and price source in `prices.py` (Q10).

### 5.2 Routing stays in code (Veeru confirms by merging)
`services/api/app/ai/routing.py` (owned by ai-engineer) holds a typed table that maps features to provider, model ID and fallback. It follows CLAUDE.md:

| Feature group | Provider | Model (inference profile from ap-south-1) | Fallback |
| --- | --- | --- | --- |
| drawings, documents (`rfq_from_drawing`, `doc_check`, `profile_codes`, `quote_draft`) | bedrock | Sonnet: `global.anthropic.claude-sonnet-5-5` | Opus `global.anthropic.claude-opus-5-5` when confidence is low |
| masking, matching, alerts (`masking`, `matching`, `rules_watch` alerts) | bedrock | Haiku role: `in.anthropic.claude-haiku-4-5-20251001-v1:0` | none |
| Indian languages, voice | sarvam | per Sarvam docs | none |
| `admin_provider_test` | per provider | cheapest | none |

**The founder must decide two things before go-live (Q3, Q6):**

- **Data residency.** From ap-south-1, Sonnet 5.5, Sonnet 4.6 and Opus 5.5 are offered **only** through the **Global** cross-region profile. Prompts, including drawings and documents, can therefore be processed in any commercial AWS Region. Only Haiku 4.5 has an **India** geo profile (`in.`, routing to Mumbai and Hyderabad).
  - There is no India-only option for Sonnet or Opus today, and the direct Anthropic API is not India-resident either.
  - Recommendation: accept Global for Sonnet and Opus in Phase 1, state it in the privacy terms, and keep Haiku on `in.`.
  - If not accepted, infra adds an IAM Deny on `aws:RequestedRegion = "unspecified"`, which blocks Global routing, and the drawing and document features cannot run.
- **Haiku's future.** Haiku 4.5's model card says "EOL no sooner than Oct 16, 2026". ai-engineer must confirm what replaces it for the Haiku role before M1.
- **Structured output.** Bedrock's native structured outputs are not available for Sonnet 5.5 or Opus 5.5, nor for Haiku through `in.`. The gateway keeps the ai-engineer rule: validate with Pydantic, retry once, then return a typed error.

**Why routing is not editable at runtime:** a model change without an eval run would bypass the pass marks that block PRs. The admin page shows routing **read-only**, with the git SHA. The only runtime controls are provider enable or disable and caps (including a cap of 0 per feature).

### 5.3 How the gateway resolves credentials and routing at runtime (ai-engineer)

New modules:
- `app/ai/secrets.py`: a `SecretStore` Protocol with `get(name) -> SecretValue(value, version_id)` and `invalidate(name)`. It has three implementations:
  - `AwsSecretStore`: boto3 `secretsmanager`, region `ap-south-1`.
  - `InMemorySecretStore`: for tests.
  - `EnvSecretStore`: `ORSYN_SECRET__<PROVIDER>`, allowed only when `ORSYN_ENV=local`.
- `app/ai/providers/bedrock.py`: boto3 `bedrock-runtime` **Converse** API, `region_name=ORSYN_BEDROCK_REGION` (default `ap-south-1`), model IDs from `routing.py`. Credentials come from the default chain (the ECS task role). There is no key code path.
- `app/ai/providers/sarvam.py`: an httpx client. Each call gets the key from `SecretStore` and sends it in the vendor's auth header. The key is never logged; httpx event hooks redact the header.
- `app/ai/prices.py`: Decimal USD per 1M input and output tokens per `model_id`. Each row has `source_url` and `checked_on`.
- `app/ai/limits.py`: spend-cap and enabled checks.

**Each `Gateway.complete(req)` runs in this order:**
1. Resolve the route for `req.feature` from `routing.py`. An unknown feature raises `RouteNotFound`.
2. Check whether the provider is enabled: read `provider_credentials`, **cached for 30 s** per task. If it is disabled, write a `model_calls` row with status `blocked_disabled` and raise `ProviderDisabled`.
3. Check spend caps: load active caps (cached 60 s) that match (`org_id`, `feature`), and sum month-to-date `model_calls.cost_amount` for each matching scope (an indexed SQL sum).
   - If MTD ≥ limit: write `blocked_cap` and raise `SpendCapExceeded`.
   - If the crossing is new, emit the alert event or log.
   - Overshoot is bounded by the calls already in flight. This is accepted and documented.
4. Get credentials: for `api_key` providers, `SecretStore.get`, **cached in-process for 5 minutes**. A missing or unreadable secret raises `ProviderUnavailable(missing_secret)`.
5. Call the provider with a timeout and one retry (as in E0). On 401 or 403 from an API-key provider: `invalidate`, refetch once, retry once. This is how a rotation is picked up early. If it still fails, raise `ProviderAuthFailed`.
6. Compute cost **in code**, write the `model_calls` row and the E0 log line, and return.

**Fail-closed rules:**
- There is no fallback to another provider, to a hardcoded or env key, or to the fake provider.
- Typed errors reach the agent, which returns a plain "temporarily unavailable" error to the user.
- `ORSYN_AI_PROVIDER` becomes `Literal["fake", "live"]`. A validator refuses `fake` when `ORSYN_ENV=prod`.

**Rotation without a redeploy:**
- After an admin write, the writing task sees the new key at once; other tasks see it within 5 minutes, or on the first 401.
- Vendor runbook: create the new key at the vendor, paste it in admin, test, wait 10 minutes, then revoke the old key at the vendor.

**Dev and CI stay offline:**
- `ORSYN_AI_PROVIDER=fake` is the default (E0).
- Bedrock tests use `botocore.stub.Stubber`. Sarvam tests use `httpx.MockTransport`. Secrets use `InMemorySecretStore`.
- `pytest-socket` (`--disable-socket --allow-unix-socket`) makes any real network call fail the test run. It is a new dev dependency, justified by this rule.
- No AWS credentials exist in CI.
- Locally, a developer may opt in to `live` with their own AWS SSO profile and `EnvSecretStore`. That is documented, never the default.

---

## 6. Rules

None from `packages/rules` are read. Prices are not rules; they live in `app/ai/prices.py` with a source URL and checked date per row.

A test fails if any price's `checked_on` is more than 90 days old, so prices get re-checked. No requirement goes into any prompt; the probe prompt is a fixed connectivity string.

---

## 7. Screens

`docs/screens.md` does not exist, so frontend builds to `.claude/agents/frontend.md` and this section. The founders should add these screens to `screens.md` (Q12).

**Placement:**
- The screens are an admin route group in `apps/web`: `app/(admin)/admin/...`. Next middleware returns 404 for `/admin` unless `Host` is the admin host.
- On the admin host, the ALB sends `/api/*` to the api target group, so calls are same-origin.
- They reuse E0's `AppShell`. The side panel has Providers, Routing, Spend caps, Costs and Audit.
- The top bar shows "Orsyn admin" plus the environment as text: `dev` in muted, **`prod` in warn colour** so nobody edits prod by mistake.
- Desktop-first at 1440px, usable at 390px. Light theme, the E0 tokens, one `h1` per screen, no intro paragraphs.
- Status is coloured text: Configured = ok, Missing = warn, Failing = bad, Disabled = muted.
- Key tails, model IDs and amounts use IBM Plex Mono. Times show as `05 Oct 2026, 14:32 IST`.
- Amounts show as `US$ 1,234.5678` with en-IN digit grouping (Q9). Every number comes from the server; nothing is summed in the browser.

| Screen | Holds | Empty | Loading | Error |
| --- | --- | --- | --- | --- |
| **Providers** `/admin/providers` | Table: provider, auth (IAM role / API key), status, key (`•••• 7f3a` or "Not used" for Bedrock), rotated at, last test (time, result, cost) | "No providers configured." (only if the seed is missing) | skeleton rows | "Couldn't load providers." + Retry |
| **Provider detail** `/admin/providers/[p]` | Rows: status, auth, region (Bedrock), models used (from routing), key last 4, rotated at/by, "Changed outside admin" note, last test. Actions (owner only, hidden for viewer): **Set key / Rotate key**, **Test connection**, **Disable / Enable** (with a reason). Recent changes (≤10 events) | "No changes yet." | skeleton | inline error per action: plain cause from `error.code` (e.g. "The key was rejected by Sarvam."), never the raw vendor text |
| **Set or rotate key** (dialog) | Password input (`autocomplete="new-password"`, never prefilled, cleared after submit), a "type the provider name to confirm" field, and Save | n/a | button shows "Saving…", disabled | 409/422/502 shown under the field. **Sent with a plain `fetch`, not stored in TanStack Query's mutation cache** (the cache keeps `variables`), and never put in component state after submit |
| **Routing** `/admin/routing` | Read-only table: feature, provider, model ID, fallback and rule, max tokens. Footer row: "Source: routing.py @ `<sha>`" | "No routes defined." | skeleton | error + Retry |
| **Spend caps** `/admin/spend` | Table: scope (all / customer name / feature), limit, month-to-date, % used, state (ok / Alerting in warn / Blocked in bad). Owner: add or edit cap (scope, limit, alert %), deactivate | "No caps. The gateway is not limiting spend." in warn colour | skeleton | error + Retry |
| **Costs** `/admin/costs` | Month picker (IST months). Cards: total, calls, errors. Tables by feature, by customer, by model, by provider (TanStack Table, sortable). Recent calls (paginated, no text) | "No model calls in October 2026." | skeleton | error + Retry |
| **Audit** `/admin/audit` | Event list: time, actor, type, subject, short payload summary | "No admin activity yet." | skeleton | error + Retry |
| **No access** | Shown on 403: "You don't have admin access." with no further detail | | | |

Accessibility: real buttons, labelled inputs, 44px targets, 4.5:1 contrast. Strings are ready for translation, but the admin area is English-only for now.

---

## 8. Tests and evals (qa-evals; api tests in `services/api/tests/`, web tests in `apps/web/tests/` as decided in E0 §1.3)

### 8.1 One test per proposed "Done when" clause
| Clause | Test |
| --- | --- |
| (a) only admins; every action audited | `test_admin_access_only_active_staff`: no JWT → 401; bad signature, wrong `signer` or expired → 401; valid JWT for an email not in `staff_admins` → 403 plus an `admin.access_denied` event; inactive → 403; viewer → 200 on GET. `test_every_admin_mutation_writes_event`: parametrised over every mutating route, each writes exactly one event with actor, source `admin_ui`, `request_id` and `client_ip` |
| (b) key only in Secrets Manager; only last 4 shown | `test_set_key_stores_only_in_secret_store`: after PUT, `InMemorySecretStore` has the key. A **scan of every text and jsonb column in every table** does not find it. GET responses contain only `key_last4`. Captured logs (caplog, all levels) do not contain it. Event payloads do not contain it. The 422, 409 and 502 bodies do not echo it |
| (c) test connection: one gateway call, cost logged | `test_provider_test_makes_one_gateway_call_and_logs_cost`: the stubbed Bedrock Converse is called exactly once. One `model_calls` row has feature `admin_provider_test`, Decimal cost equal to tokens × the `prices.py` row, and a `price_ref`. A `provider.test_run` event links `model_call_id`. A second call within 30 s returns 429 with no provider call |
| (d) rotation without redeploy; fail closed | `test_rotation_picked_up_after_ttl` (frozen time: old key before 5 minutes, new after). `test_401_invalidates_and_refetches_once`. `test_missing_secret_fails_closed` (no provider call, `unavailable` row, typed error). `test_disabled_provider_refused`. `test_spend_cap_blocks_before_call` (MTD ≥ limit → no provider call, `blocked_cap` row, `SpendCapExceeded`). `test_cap_zero_is_feature_kill_switch`. `test_no_fallback_to_fake_or_env_in_prod` |
| (e) MTD spend by feature, customer and model against caps | `test_costs_summary_sums_in_sql_decimal`: fixture rows in two IST months, checking the boundary at 18:30 UTC on the last day. Totals equal Decimal sums and are strings. `test_spend_caps_state`: ok / alerting at `alert_pct` / blocked, plus a one-time `spend_cap.alert_crossed` event |

### 8.2 Negative tests (always)
- **Org isolation:**
  - `model_calls` and cost repository functions take either an `org_id` or an explicit `PlatformScope` object, and the `PlatformScope` object can only be built by the admin dependency. A customer-context call raises.
  - Customer-host requests to `/admin/*` return 404.
  - A customer credential, once the customer auth story lands, on an admin route returns 401. Until then there is a placeholder test that admin routes ignore `Authorization: Bearer`.
- **Masking:**
  - `model_calls` has no free-text column (a schema assertion).
  - Cost and audit responses contain org names and ids only: the test scans responses for e-mail and phone patterns.
  - The probe prompt contains no customer data.
  - Masking-before-award in its normal sense does not apply (no supplier contacts are touched); the PR states this.
- **Approval required:** no customer-facing outbound path is added. The test-connection call is itself the human action. `test_no_admin_route_sends_customer_outbound` asserts that no admin route imports `approvals` senders, WhatsApp or email. Stated in the PR.
- **Auth and transport:**
  - `dev_header` mode is refused at startup when `ORSYN_ENV ∈ {dev, prod}`.
  - Mutations without `X-Orsyn-Admin`, with a wrong `Origin` or with a non-JSON body → 403.
  - Wrong `Host` → 404.
  - Admin routes are absent from `/openapi.json`.
- **Gateway hygiene:** E0's `test_no_direct_model_calls.py` is extended:
  - `boto3` clients for `bedrock-runtime` and `secretsmanager`, and `httpx` calls to vendor hosts, may appear only under `app/ai/`;
  - `pytest-socket` blocks network in all tests.
- **Prices:** `test_prices_decimal_and_fresh`: all Decimal, every model in `routing.py` has a price, and `checked_on` is no more than 90 days old.
- **Web:**
  - the key form clears its input after submit and never renders a saved value;
  - viewer sees no action buttons;
  - each screen's empty, loading and error states render;
  - the prod environment label is shown.

### 8.3 Evals
No agent or prompt-for-agent changes, so no agent eval suite is added. E0's `_smoke` suite must stay at 100% after the gateway changes, with cost 0. Real-provider canaries are manual (Veeru presses "Test connection" in dev after setup).

---

## 9. Cost

**Model calls per user action:**

| Action | Model calls |
| --- | --- |
| All admin reads and writes | **0** |
| **Test connection** | **1** call, feature `admin_provider_test`, about 20 input and 5 output tokens: **under US$0.001 per test** on any routed Claude model (Haiku-role ≈ US$0.0001). Exact figures come from `prices.py` |

The gateway adds 1 indexed SQL sum and 1 insert per model call. There is no extra model cost.

**AWS, new and recurring, per environment** (list prices; infra confirms):
- Secrets Manager: 4 secrets (anthropic, sarvam, whatsapp_cloud, gst_lookup) × US$0.40 = US$1.60. API calls with a 5-minute cache ≈ 9k per secret per task per month ≈ US$0.05 each.
- CloudWatch: 2 metric filters plus 2 alarms ≈ US$0.20. SNS email: within the free tier.
- ALB OIDC authentication, the source-ip rule, the default KMS key and AWS Budgets (first 2 budgets): US$0.
- **Expected monthly change ≈ US$2 (≈ ₹170 at an assumed ₹85/US$) per environment, so about US$4 (≈ ₹340) for dev plus prod.**
- The IdP is the company's existing Google Workspace, so US$0. If Cognito is used instead (Q4), its free tier covers fewer than 10 staff.

**Monthly manual check:** compare the admin "Costs" total with AWS Cost Explorer. Bedrock third-party models bill **through AWS Marketplace under the model provider, not under "Amazon Bedrock"**. Do the same comparison against Sarvam's billing page.

---

## 10. PR split

**Prerequisites:**
- E0 merged, specifically E0 PR 1 (api skeleton, settings) and PR 2 (gateway interface, `FakeProvider`, evals runner).
- E0c DB baseline (Q2).

**E0b does not block E0.** It edits E0 files only after E0 merges, and the only E0 contracts it extends are the `ORSYN_AI_PROVIDER` literal and the no-direct-calls test. PRs 1–7 run fully offline. PR 8 waits for the AWS account and the IaC choice (E0 Q1).

| # | PR | Builder(s) | ~Lines | Labels |
| --- | --- | --- | --- | --- |
| 1 | Migration (reversible) for `staff_admins`, `provider_credentials` (+ seed rows), `spend_caps` (+ global fuse), `model_calls` (+ append-only trigger); SQLAlchemy models, repositories with the `org_id` / `PlatformScope` guard; tests | backend, qa-evals | ~350 | needs-founder, security-review |
| 2 | Admin auth: ALB JWT verifier (`pyjwt[crypto]`, new dep, justified; infra confirms the ALB JWT padding quirk in its test vectors), `staff_admins` lookup, roles, host, CSRF and Origin checks, `dev_header` local mode with startup guard, bootstrap CLI, `audit()` event helper, `GET /me`; tests | backend, qa-evals | ~380 | needs-founder, security-review |
| 3 | Gateway core: `SecretStore` (AWS, in-memory, env-local) with TTL cache and invalidate; enabled check; spend-cap check; `model_calls` write; typed errors; `prices.py`; `ORSYN_AI_PROVIDER` gains `live` with the prod guard; `pytest-socket`; tests | ai-engineer, qa-evals | ~390 | needs-founder, security-review |
| 4 | Providers: Bedrock Converse adapter (Stubber tests), Sarvam adapter (MockTransport tests), `routing.py` per §5.2, prompt `provider_test` v1; `_smoke` still green | ai-engineer, qa-evals | ~380 | security-review |
| 5 | Admin API (providers): list, detail, set or rotate key (`PutSecretValue`), test, enable, disable, routing read, audit read; tests | backend, qa-evals | ~380 | needs-founder, security-review |
| 6 | Admin API (spend): spend-caps CRUD, costs summary and calls, `admin.viewed` throttling; tests | backend, qa-evals | ~320 | security-review |
| 7 | Web (1): admin route group, host middleware, admin nav in shell, env label, Providers list, Provider detail, key dialog (plain fetch), test and enable/disable actions; tests | frontend, qa-evals | ~390 | security-review |
| 8 | Web (2): Routing, Spend caps, Costs, Audit, No access screens; tests | frontend, qa-evals | ~380 | |
| 9 | Infra (after AWS account and IaC tool), detailed below | infra | ~300 | needs-founder, security-review |

**PR 9 contents:**
- Placeholder secrets `orsyn/<env>/providers/*`.
- ECS task role policy:
  - `bedrock:InvokeModel` and `InvokeModelWithResponseStream` only on the inference-profile ARNs in `routing.py`, plus their foundation-model ARNs. For Global profiles that includes `arn:aws:bedrock:::foundation-model/<id>`, with a `bedrock:InferenceProfileArn` condition.
  - `secretsmanager:GetSecretValue` and `PutSecretValue` on the placeholder ARNs only.
  - **no** `aws-marketplace:*`, no `CreateSecret` or `DeleteSecret`.
- An explicit Deny on Bedrock API-key (bearer token) use.
- ALB admin host rule with `authenticate-oidc` (client secret held as a sensitive value) and an optional `source-ip` condition; `/api/*` routed to the api.
- ACM certificate and DNS for `admin.<domain>`.
- Metric filters, alarms, SNS topic, AWS Budget.
- Monthly cost note.

PRs 1 → 2 → 3 are sequential. 4 follows 3. 5 needs 2, 3 and 4. 6 needs 5. 7 needs 5; 8 needs 6 and 7. 9 can be reviewed in parallel with 5–8 but merges last. **security-reviewer is required on PRs 1–7 and 9; product-reviewer checks the story at the end.**

**File ownership** (no overlap):
- backend: `app/admin/**`, `app/db/**`, migrations.
- ai-engineer: `app/ai/**`.
- frontend: `apps/web/app/(admin)/**`, `apps/web/middleware.ts`.
- infra: `infra/**`.
- qa-evals: tests.
- `pyproject.toml` stays with backend, which adds `pyjwt[crypto]`, `boto3` and `pytest-socket` in PR 1.

---

## 11. Flags

- **needs-founder: yes.** It touches every trigger:
  - **migrations**: four new tables plus a dependency on the DB baseline;
  - a **login path**: new staff authentication through ALB OIDC and `staff_admins`;
  - **secrets**: the write path into Secrets Manager and the IAM that permits it;
  - **spend**: live provider calls, spend caps, and the global fuse value.

  The data-residency choice (Q3) is also a founder decision.
- **security-review: yes**, for:
  - **auth**: JWT verification, roles, CSRF, the host split and the dev-mode guard;
  - **isolation**: staff reading cross-org cost data, and the `PlatformScope` guard;
  - **secrets**: write-only handling, logging, events, the browser cache and the error echo;
  - **IAM**: Bedrock profile-scoped ARNs, the Secrets Manager scope, no Marketplace actions;
  - outbound calls to vendors.
- `rules-change`: no.

---

## 12. Open questions

1. **Story key and "Done when".** `E0b` is provisional, and `docs/build-plan.md` does not exist. Please confirm the key, the milestone label (M1?) and the proposed "Done when" in §1.
2. **DB baseline.** Create a small **E0c** story (Alembic, Postgres in CI, `orgs` with a platform org, `events`) before E0b and M1? Or should E0b's PR 1 carry it? The recommendation is E0c, because `orgs` and `events` are core ontology and deserve their own plan.
3. **Data residency.** From ap-south-1, Sonnet and Opus are reachable only through the **Global** profile, which may process prompts outside India. Accept it for Phase 1 (recommended, disclosed in privacy terms, after counsel checks it under the DPDP Act)? Or block Global, which leaves no drawing or document features on Bedrock?
4. **Staff IdP.** Is Orsyn on Google Workspace with 2-step verification enforced? If not, use a dedicated Cognito user pool with TOTP MFA required and no self sign-up.
5. **IP allow-list.** Is there a static office or VPN IP to add to the admin host? The default is off.
6. **Models.** Confirm Sonnet 5.5 and Opus 5.5 for drawings and documents. Which model takes the **Haiku role**, given Haiku 4.5 is "EOL no sooner than 2026-10-16"? ai-engineer to propose with eval results.
7. **Direct Anthropic API.** Is it needed in Phase 1, as a fallback or for features Bedrock lacks? If yes, it becomes a follow-up PR: adapter, transport switch, and its own residency and terms review. The default is Bedrock only.
8. **Cap values.** What global monthly fuse for dev and for prod (for example US$50 and US$500)? Is the default alert at 80% right? Should the per-customer default cap be set at org creation?
9. **Currency on screen.** Show costs in USD only (recommended: providers bill in USD), or also in ₹? ₹ needs an FX source with a date, and computing with it is money maths that needs a rule source.
10. **Sarvam.** Which plan or account, and which endpoint is cheapest for the probe? ai-engineer confirms the auth header and prices from Sarvam's docs.
11. **AWS accounts.** One account with env tags, or separate dev and prod accounts under AWS Organizations (recommended for blast radius)? The Anthropic first-use form submitted in the management account is inherited by the member accounts. Also confirm infra may deny Bedrock long-term API keys account-wide.
12. **`docs/screens.md`.** Who adds the admin screens (§7) to it, and do the founders want to see a sketch before PR 7?
13. **Two-person rule.** Should key rotation, disable and cap changes need a second owner's approval? The default is single owner plus audit, so an emergency rotation is not blocked.

---

## Appendix A — Veeru's manual checklist

**AWS account and identity**
- [ ] Create the AWS account(s) (Q11). Turn on root MFA, set a billing contact, set a valid payment method (needed for Marketplace model billing), and lock the root keys.
- [ ] Set up IAM Identity Center for humans. Create no IAM users with access keys.
- [ ] Create AWS Budgets: total account, plus one filtered to Marketplace (Anthropic) charges, with email alerts.

**Bedrock in ap-south-1**
- [ ] Submit the **Anthropic first-time-use form** once (Bedrock console → pick an Anthropic model, or `PutUseCaseForModelAccess`). You need the company name, website and use case. With an AWS Organization, do it in the management account.
- [ ] As an admin with `aws-marketplace:Subscribe`, **invoke each routed model once** from the console playground in ap-south-1. This auto-subscribes the account. Confirm with `aws bedrock get-foundation-model-availability --model-id <id> --region ap-south-1` (`AVAILABLE` / `AUTHORIZED`). The app's task role never gets Marketplace permissions.
- [ ] Record the inference profiles callable from Mumbai and their destination Regions: `aws bedrock list-inference-profiles --region ap-south-1 --type-equals SYSTEM_DEFINED`, then `get-inference-profile` for each. Paste the result into `docs/architecture.md`, and decide Q3.
- [ ] In **Service Quotas** → Amazon Bedrock (ap-south-1), check tokens per minute and requests per minute for each profile used (Global and `in.` quotas are separate). Request increases before the first customer.
- [ ] Leave **model invocation logging off**.

**Keys and vendors**
- [ ] Sarvam: create the account and an API key. Paste the key in Admin → Providers → Sarvam → Set key (or `aws secretsmanager put-secret-value --secret-id orsyn/<env>/providers/sarvam --secret-string '{"api_key":"…"}'` from a trusted terminal), then press Test connection.
- [ ] Direct Anthropic API: only if Q7 is yes. Create the org at console.anthropic.com, set a monthly spend limit there, create a workspace key, then put it in the same way as Sarvam.
- [ ] WhatsApp and GST lookup: later stories; leave them "Missing".
- [ ] Never paste a key into chat, a PR, a ticket, `.env.example` or Slack.

**Admin access**
- [ ] IdP: create an OAuth client for `https://admin.<domain>/oauth2/idpresponse` and enforce 2-step verification for the Orsyn domain (Q4). infra stores the client secret.
- [ ] DNS and certificate for `admin.<domain>` (infra PR 9).
- [ ] Bootstrap the first owner: `uv run python -m app.admin.bootstrap --email <you> --role owner`, run as an ECS one-off task. Add Nithish.
- [ ] Set the global spend fuse and any per-feature caps (Q8).

**Monthly**
- [ ] Compare Admin → Costs with Cost Explorer (Marketplace → Anthropic) and with the Sarvam bill. Investigate any gap above 5%.
- [ ] Re-check `prices.py` dates. The test fails after 90 days.
