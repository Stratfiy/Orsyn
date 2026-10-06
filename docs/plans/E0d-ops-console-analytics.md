# E0d — Ops console: KPIs, AI usage, events, outcomes, issues and product analytics

Status: draft, waiting for founder OK. Author: architect. Date: 2026-10-05. Story key is **provisional** (Q1).

Inputs read: `CLAUDE.md`, `KICKOFF.md`, `.claude/agents/{infra,backend,ai-engineer,frontend,security-reviewer}.md`, `docs/plans/E0-repo-ci.md`, `docs/plans/E0b-admin-provider-keys.md`. **Missing:** `docs/build-plan.md`, `docs/screens.md`, `docs/architecture.md` and all code. This plan builds on E0 (settings, gateway, CI), **E0b** (admin host, ALB OIDC sign-in, `staff_admins`, `PlatformScope`, `model_calls`, audit helper, SNS alerts) and **E0c** (Alembic, `orgs` with a platform org, append-only `events`). It changes nothing in those plans; where it needs more from them it says so as an additive migration or a contract (§2.6).

PostHog session-replay option names were checked on 2026-10-05 against PostHog's replay privacy docs; Sentry plan prices against sentry.io/pricing. infra re-checks both at build time.

Founder's ask, verbatim: "PostHog event and all metrics and KPIs. I should be able to see revenue, token usage, events, outcomes, resolve issues and don't have to keep going to EC2 again and again."

---

## 1. Goal

Extend the E0b admin area into one staff-only **ops console** where the founders read the business (KPIs, AI usage and margin, events, agent outcomes) and fix problems (grouped errors with their log lines, dependency health, failed jobs, stuck approvals, a per-customer support view, a few safe audited actions) without SSH, the AWS console or grepping logs. Add PostHog for product analytics only.

> Done when (**proposed**; `docs/build-plan.md` does not exist, the founder confirms the text, Q1):
> (a) an owner or viewer can open each KPI in §1.3 for any IST date range, filter by customer, and every figure links to the rows it was computed from; KPIs whose source tables do not exist yet say "Available after M1" or "after M2";
> (b) the AI usage page shows tokens, cost, latency (p50/p95), error rate and the latest eval score by feature, model and customer, and margin per customer, all from `model_calls` and stored data;
> (c) the events explorer finds events by org, RFQ, PO and actor; supplier and buyer contacts stay masked; only an owner can reveal one contact, with a reason, and the reveal is in the event log;
> (d) the outcomes page shows, per agent and prompt version, how many drafts were approved as-is, edited or rejected, from `approvals`;
> (e) an unhandled API or job error shows up as a grouped issue within one minute, and its log lines open in the console by request id;
> (f) the health page shows the state of the database, queues, Bedrock, Sarvam, email, WhatsApp and the api and worker services;
> (g) a failed job (SQS DLQ) can be viewed, retried or discarded by an owner, each with a reason and an event;
> (h) founders get an email within 10 minutes of an error spike, a failed job, a provider outage, a cost spike, a spend-cap block or the site going down;
> (i) PostHog receives only the tracking-plan events, identified by internal ids only, never on the admin host, and nothing is sent when its key is absent;
> (j) every console action writes an event, and no console action changes money or deletes business data.

### 1.1 "Going to the server", and what replaces it

We run on **ECS Fargate**: there is no EC2 host to SSH into, by design. Each old habit maps to a console page.

| Old task | Replacement in the console |
| --- | --- |
| SSH in and `tail`/`grep` logs | **Errors** page groups exceptions; each occurrence opens its **log lines by request id** (CloudWatch Logs Insights, run by the api). Customer error pages show "Reference: `<request id>`", which staff paste into the search box |
| "Is the server up? Which version is live?" | **Health** page: ECS running vs desired tasks and git SHA per service, DB latency, RDS CPU and free storage, queue depths, providers, email, WhatsApp. An external Route 53 health check emails if the site is down |
| Restart a stuck process | Not needed: ECS replaces tasks that fail health checks. A console "restart" is **not built** (Q11) |
| Check whether a cron or job ran; re-run it | **Jobs** page: last run of each schedule (from `job.*` events), failed jobs from the DLQ with **Retry** / **Discard** |
| Run SQL to look at a customer | **Customers** support view (timeline, open issues, failed jobs, pending approvals, AI cost) and the **Events** explorer. No SQL console |
| Check token spend in the AWS bill | **AI usage** page (from `model_calls`) plus daily infra cost from the Cost Explorer API |
| Run a migration or one-off script | Unchanged: an ECS one-off task from a reviewed PR (E0b bootstrap pattern). Never from the console |

### 1.2 Design choices (simplest that meets "Done when")

- **One app.** Same `admin.<domain>` host, same ALB OIDC sign-in, same `staff_admins` roles (viewer reads, owner acts), same audit helper and `PlatformScope` as E0b. New pages join the same side panel.
- **KPIs are live SQL queries**, not a daily rollup table. Phase 1 volumes are hundreds of RFQs; a rollup adds a job, backfill and staleness. Each KPI is one function in a registry (`app/ops/kpis.py`) that returns value, numerator, denominator and the ids of its source rows. Results are cached in-process for 5 minutes. Revisit a rollup when any KPI query exceeds 1 s at p95.
- **Errors: CloudWatch Logs + our own `error_groups` table, no Sentry** (§1.5).
- **Failed jobs are copied from the DLQ into Postgres** (`failed_jobs`) by a drain consumer, so viewing never changes SQS visibility and every retry/discard is a row plus an event.
- **Health is computed on request** (cached 30 s), with no health table. Providers are judged passively from `model_calls` (no probe spend); the owner's E0b "Test connection" stays the active probe.
- **PostHog is product analytics only.** Business KPIs come from our DB, never from PostHog (§1.6).
- **No new model calls.** Nothing in the console asks a model to summarise or explain.

### 1.3 KPI definitions

All periods are IST calendar days/months; boundaries computed in code, stored and queried in UTC. All KPIs **exclude orgs with `is_test = true`** (§2.5). "Matured RFQ" = an RFQ sent at least **7 days** ago or closed (Q13). Money is `Decimal` per currency, never summed across currencies, never FX-converted unless Q3 adds a rate rule. The table names below are the **contract with the M1/M2 plans** (§2.6); exact names align when those plans land.

| KPI | Formula | Source | Grain | Available |
| --- | --- | --- | --- | --- |
| RFQs sent | count of `rfqs` with `sent_at` in period | `rfqs` | day, total; by buyer org | M1 |
| Quotes per RFQ | for matured RFQs sent in period: distinct suppliers with ≥1 submitted `quote_versions` row ÷ RFQs; show mean and median | `rfqs`, `quote_versions` | period; by buyer org | M1 |
| Supplier reply rate | invites with ≥1 submitted quote ÷ invites sent, matured RFQs | `rfq_invites`, `quote_versions` | period; by supplier org | M1 |
| Supplier reply time | per invite: first `quote_versions.submitted_at` − `rfq_invites.sent_at`; median and p90 over replied invites | same | period; by supplier org | M1 |
| Time to first quote | per RFQ: min(`quote_versions.submitted_at`) − `rfqs.sent_at`; median and p90 over RFQs with ≥1 quote | `rfqs`, `quote_versions` | period | M1 |
| Supplier activation | cohort: supplier orgs created in month M whose first quote is submitted within **30 days** of org creation ÷ supplier orgs created in M | `orgs`, `quote_versions` | month cohort | M1 |
| Buyer repeat | cohort: buyer orgs whose first RFQ was sent in month M and who sent a second RFQ within **90 days** ÷ buyer orgs with first RFQ in M | `rfqs` | month cohort | M1 |
| Award rate | matured RFQs sent in period with an award ÷ matured RFQs sent in period | `rfqs`, `awards` | period; by buyer org | M2 |
| GMV | Σ `po_lines.line_amount` (ex-GST, `Decimal`) of POs with `issued_at` in period, **per currency** | `pos`, `po_lines` | day, month; by buyer and supplier org | M2 |
| Revenue | **Undefined until Q2.** Recommended if the model is a commission: Σ (`po_lines.line_amount` × the org's contracted rate from `commercial_terms`, with a contract reference), computed in code, per currency | `po_lines`, `commercial_terms` | month; by org | M2 + Q2 |
| Take rate | Revenue ÷ GMV, per currency | above | month | M2 + Q2 |
| AI cost per RFQ | (Σ `model_calls.cost_amount` for RFQ-loop features `rfq_from_drawing`, `matching`, `masking`, `quote_draft`) ÷ RFQs sent, in period, USD. A **period average**: per-RFQ exact cost needs a subject link on `model_calls` (deferred) | `model_calls`, `rfqs` | month | M1 |
| Cost per RFQ (all-in) | AI cost per RFQ + (allocated infra USD ÷ RFQs sent) | + `infra_costs_daily` | month | M1 |
| Margin per customer | Revenue − AI cost (exact, `model_calls.org_id`) − allocated infra (monthly infra total × the org's share of RFQs sent + quotes submitted, Q12). Shown per currency; one figure only when Q3 provides FX | `model_calls`, `infra_costs_daily`, revenue | month; by org | M2 + Q2 |

Every value returned carries `numerator`, `denominator`, `source_tables` and a `rows` link (§3.7) so CLAUDE.md rules 2 and 3 hold: numbers are computed in code from stored rows, and each one opens its source rows.

### 1.4 Contact masking for staff (proposed rule, Q8)

1. Every console response passes supplier and buyer contact fields (phone, email, website, address lines) through the **same masking serializer** the customer API uses. Staff get no implicit exemption, before or after award.
2. Event payloads, `failed_jobs.payload`, error rows and log lines must not contain contacts at all (write-time rule, tested). The console re-masks anyway as a second layer.
3. An **owner** may reveal the contacts of **one** org or person: they pick a reason code (`support_request`, `verification`, `fraud_or_abuse`, `legal_request`) and write a note (10–200 characters). The reveal lasts 15 minutes for that staff member and subject only. It writes `staff.contact_revealed` and emails the other owners through the info alert topic.
4. Viewers cannot reveal. There is no bulk reveal, no reveal in lists or exports, and no reveal in the events explorer or log viewer. Reveals happen only on the support view's org card.

### 1.5 Errors: CloudWatch-only plus an `error_groups` table (Sentry not chosen)

| | CloudWatch + `error_groups` (chosen) | Sentry Team |
| --- | --- | --- |
| Cost | ≈ US$0 extra (logs already paid) | from US$26/mo billed annually (Developer is free but 1 user only) |
| Data location | ap-south-1, with the rest of our data | US or EU, a new processor of stack traces |
| Masking risk | we control every field; no message text in Postgres | stack locals and request data must be scrubbed; one missed setting leaks contacts (rule 5) |
| Fit | groups live in the same console as the customer, jobs and events | another login and another place to look |
| Gap | **no browser errors**, simpler grouping | browser errors, source maps, release health |

Decision: CloudWatch-only, because it keeps contacts and drawings inside our boundary, adds no vendor or secret, and puts errors next to the support view. **Browser JS errors are deliberately not captured** in this story. The trigger to revisit: the first customer-reported UI bug we cannot reproduce. The fix then is Sentry Team in the EU region with `send_default_pii=False` and no request bodies (Q4).

How it works:
- A request-id middleware takes `X-Amzn-Trace-Id` or makes a uuid, returns `X-Request-Id`, and puts `request_id` on every JSON log line, event, `model_calls` row and error row.
- A logging filter masks email and phone patterns in every log record before it is written.
- The FastAPI exception handler and the SQS job runner wrapper compute `fingerprint = sha256(kind + exception class + innermost in-app frame module:function + route template or job type)`. They upsert `error_groups` and insert `error_occurrences`, then log one `orsyn.error` line with the full traceback. Capture is best effort: if the DB is down, only the log line is written.
- Postgres holds no exception message text. The message is in CloudWatch (masked), one click away.

### 1.6 PostHog (product analytics only)

- **Region and identity:** EU Cloud (`https://eu.i.posthog.com`). `distinct_id` is the internal person uuid. `org_id` and `org_kind` are event properties (super properties on the client). Group analytics (a paid add-on) is not used. No email, phone, name, company name, GSTIN, file name, amount or free text is ever sent.
- **Off by default:** web reads `NEXT_PUBLIC_POSTHOG_KEY`, api reads `ORSYN_POSTHOG_KEY`; when either is absent, that side sends nothing and the wrapper is a no-op. **Never initialised on the admin host.** Off in `local` and in CI.
- **Client config** (frontend verifies option names against the pinned posthog-js version):
  - `autocapture: false`; `capture_pageview: "history_change"`;
  - `mask_all_text: true`, `mask_all_element_attributes: true`;
  - `person_profiles: "identified_only"`; `disable_surveys: true`;
  - `session_recording: { maskAllInputs: true, maskTextSelector: "*", blockSelector: "[data-ph-block]" }`; canvas recording off. Drawing viewers and document previews carry `data-ph-block`;
  - `before_send` strips query strings and fragments from `$current_url`, `$pathname` and `$referrer`, and drops any property not in the tracking plan.
- **Project settings** (Veeru): "Discard client IP data" on, replay sampling (Q7), billing limit set so spend stays US$0.
- **Calls:** `identify(person_id)` after login; `reset()` on logout. CSP `connect-src` and `script-src` get the PostHog ingest and asset hosts. No reverse proxy.
- **Feature flags:** for UI rollouts only, named `ff_<area>_<name>`, evaluated client-side. When PostHog is off or a flag is undefined, the code takes the existing path. Flags **never** gate auth, `org_id` scoping, masking, approvals, rules or prices. Server-side flag evaluation is not used: it would need a personal API key, which is a secret.
- **Client vs server:** the client sends UI intent (pageviews, uploads started, drafts reviewed) and replays. The server sends **business state changes**, using **exactly the same names as `events.type`**, after the DB commit, fire-and-forget through the batching posthog-python client with `disable_geoip=True`. Server events are sent only when a person is the actor.
- **How the two relate:** our `events` table is the truth and the KPIs read it; PostHog is a lossy copy for funnels and replays. A funnel step in PostHog and a KPI in the console share the event name (for example `rfq.sent`). Counts can differ by a few percent (ad blockers, sampling), and the console number wins.
- **Enforcement:** the tracking plan is a typed registry in code: Zod in web (`lib/analytics/plan.ts`) and Pydantic in api (`app/analytics/plan.py`). `track()` accepts only registered names with their allow-listed properties.

**Tracking plan v1**

| Event | Side | Properties (all ids are internal uuids) |
| --- | --- | --- |
| `$pageview`, `$pageleave` | client | `$current_url` path only, `app` (`buyer`/`supplier`) |
| `signup_started` | client | `app`, `channel` (`web`/`whatsapp_link`) |
| `drawing_upload_started` | client | `file_kind` (`pdf`/`image`/`cad`), `size_bucket` (`<1MB`/`1-10MB`/`>10MB`) |
| `rfq_draft_reviewed` | client | `rfq_id`, `fields_edited_count` |
| `quote_draft_opened` | client | `rfq_id` |
| `onboarding_step_viewed` | client | `step` (enum) |
| `roadmap_viewed` | client | none |
| `org.created` | server | `org_kind` |
| `rfq.created` | server | `rfq_id`, `source` (`drawing`/`manual`) |
| `rfq.sent` | server | `rfq_id`, `invited_count` |
| `quote.submitted` | server | `rfq_id`, `quote_id`, `version`, `via` (`web`/`whatsapp`), `ai_drafted` (bool) |
| `approval.decided` | server | `agent`, `prompt_version`, `decision` (`approved_as_is`/`edited`/`rejected`) |
| `order.awarded` | server | `rfq_id`, `po_id` |
| `po.issued` | server | `po_id`, `line_count` |

Super properties on every event: `org_id`, `org_kind`, `app`, `release` (git SHA). **No money values go to PostHog.**

### 1.7 Deliberately not built

- **Metabase (or another BI tool).**
  - Self-hosting it on Fargate costs about US$35–45/mo (1 vCPU, 2 GB) plus an app database, and adds a second login.
  - Its raw-table access bypasses our masking serializer and `PlatformScope`.
  - Metabase Cloud is about US$100/mo and needs a network path from outside AWS Mumbai into RDS.
  - **Recommendation: not now.** Revisit when founders ask ad-hoc questions weekly that the console cannot answer. Then point it only at a read-only `reporting` schema of masked views.
- Daily KPI rollups, cohort heat-maps, chart libraries. Trends are a small inline SVG line in each KPI card, drawn from server numbers.
- Browser error capture (§1.5).
- An SQL console, a console "restart service" or "deploy" button, and customer impersonation.
- Staff approving drafts on a customer's behalf. That would break rule 1.
- Bulk retry of failed jobs; editing a job payload before retry.
- Per-RFQ exact AI cost (needs a subject link on `model_calls`).
- A daily digest email.
- Pulling PostHog data back into the console (would need a personal API key).
- WhatsApp resend (24-hour window and template rules; its own story).

---

## 2. Ontology impact

Every new table has `id` (uuid), `org_id`, `created_at` (timestamptz UTC) and `created_by` (`person:<uuid>`, `agent:<name>` or `system:<component>`), as in E0b. Ops tables belong to the **platform org** unless noted; repositories take `PlatformScope` (E0b), which only the admin dependency can build. No documents or PO lines are created, so the document-line → PO-line link does not apply; the GMV KPI reads `po_lines` through their POs only.

### 2.1 `error_groups` (platform org)
| Column | Type | Notes |
| --- | --- | --- |
| `fingerprint` | char(64) unique | §1.5 |
| `kind` | text check in (`api`,`job`) | `web` reserved for Q4 |
| `exception_type` | text | class name only |
| `location` | text | `module:function:line` of the innermost in-app frame |
| `route_or_job` | text | route template (`/v1/rfqs/{id}`) or job type |
| `first_seen_at`, `last_seen_at` | timestamptz | |
| `first_release`, `last_release` | text | git SHA |
| `occurrences_total` | int | |
| `status` | text check in (`open`,`resolved`,`ignored`) | auto-reopens if it occurs on a release other than `resolved_in_release` |
| `resolved_in_release` | text null | |
| `status_changed_at`, `status_changed_by`, `status_note` | | note ≤ 200 characters, no contacts (masked on write) |
| `created_at`, `created_by` = `system:error_capture`, `updated_at` | | |

### 2.2 `error_occurrences`
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | the affected customer org if known, else the platform org |
| `group_id` | uuid FK error_groups | |
| `request_id` | text | links to the log lines |
| `release` | text | |
| `http_status` | smallint null | |
| `actor` | text null | `person:<uuid>`, `agent:<name>` or `system:<job>` of the failing request |
| `created_at`, `created_by` = `system:error_capture` | | |

Indexes: (`group_id`, `created_at`), (`org_id`, `created_at`), (`request_id`). **Retention:** a daily scheduled job deletes rows older than 30 days, the same as the CloudWatch log retention (the links would be dead after that). This is operational telemetry, not business data; the deletion is declared here so the founder approves it (needs-founder).

### 2.3 `failed_jobs`
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | the job's org, or the platform org |
| `queue` | text | source queue name |
| `job_type` | text | |
| `sqs_message_id` | text | unique with `queue` |
| `idempotency_key` | text | from the job envelope |
| `payload` | jsonb | **ids and enums only**, validated by the job's Pydantic schema; no contacts, text or file contents |
| `receive_count` | int | |
| `first_failed_at` | timestamptz | |
| `error_group_id` | uuid FK error_groups null | the last error captured for this message id |
| `retry_of` | uuid FK failed_jobs null | set when a retried job fails again |
| `state` | text check in (`open`,`retried`,`discarded`,`succeeded_after_retry`) | |
| `state_changed_at`, `state_changed_by`, `state_reason` | | reason 3–200 characters |
| `created_at`, `created_by` = `system:dlq_drain` | | |

Rows are never deleted. Discard is a state change.

### 2.4 `infra_costs_daily` (platform org)
| Column | Type | Notes |
| --- | --- | --- |
| `usage_date` | date | Cost Explorer days are UTC; the UI labels them so |
| `service` | text | Cost Explorer `SERVICE` dimension |
| `amount` | numeric(14,6) | `Decimal` |
| `currency` | char(3) check = `USD` | |
| `counts_as_infra` | bool | false for AWS Marketplace / Bedrock model charges, which `model_calls` already counts. This avoids double counting |
| `source` | text = `aws_cost_explorer` | |
| `fetched_at` | timestamptz | Cost Explorer revises the last few days; the row is upserted on (`usage_date`, `service`) and the latest fetch wins |
| `created_at`, `created_by` = `system:cost_fetch` | | |

### 2.5 Additive columns on E0c tables (Q15: fold into E0c if it has not merged)
- `orgs.status` text check in (`active`,`suspended`) default `active`; `orgs.status_reason`, `status_changed_at`, `status_changed_by`. Matching and RFQ invites must skip `suspended` supplier orgs (contract for the matching story).
- `orgs.is_test` bool default false. Excluded from every KPI. Set only by the bootstrap-style CLI (Q12).
- `events.rfq_id`, `events.po_id` uuid null, each indexed with `created_at`. The event writer helper takes them as optional arguments; M1/M2 stories set them on every RFQ, quote, award, PO, document and shipment event. This is what makes "search by RFQ or PO" one indexed query instead of a jsonb scan.
- Extra index on `events` (`created_by`, `created_at`) for actor search.

### 2.6 Contract with later stories (read, not built here)
| Table | Columns this story reads |
| --- | --- |
| `rfqs` (M1) | `id`, `org_id` (buyer), `created_at`, `sent_at`, `status`, `closed_at` |
| `rfq_invites` (M1) | `rfq_id`, `supplier_org_id`, `sent_at` |
| `quote_versions` (M1) | `rfq_id`, `supplier_org_id`, `quote_id`, `version`, `submitted_at` |
| `approvals` (M1) | `id`, `org_id`, `agent`, `prompt_id`, `prompt_version`, `subject_type`, `subject_id`, `status` (`pending`/`approved`/`rejected`), `edited` (bool), `fields_edited_count`, `requested_at`, `decided_at`, `decided_by` |
| `awards` (M2) | `rfq_id`, `supplier_org_id`, `awarded_at` |
| `pos`, `po_lines` (M2) | `pos.issued_at`, `pos.org_id`; `po_lines.po_id`, `line_amount`, `currency` |
| `outbound_messages` (email story) | `id`, `org_id`, `approval_id`, `channel`, `status`, `sent_at`, `idempotency_key` |
| `commercial_terms` (Q2) | `org_id`, `rate`, `basis`, `contract_ref`, `valid_from`, `valid_to` |

The outcome mapping is fixed here: `approved` with `edited = false` → **approved as-is**; `approved` with `edited = true` → **edited**; `rejected` → **rejected**.

---

## 3. API

Common rules (from E0b): base `/admin/v1`, admin host only, ALB JWT plus an active `staff_admins` row, `include_in_schema=False`, CSRF header and Origin check on mutations, errors as `{"error": {"code","message"}}`, times ISO-8601 UTC (UI shows IST), money as a string decimal plus `currency`. 401/403/404 as E0b. Every cross-org read writes `admin.viewed` (throttled as in E0b). Date ranges are required where listed and capped at **93 days** (422 `range_too_long`). Lists use cursor pagination, 50 per page.

### 3.1 KPIs
| Method and path | Who | Request | Response | Errors |
| --- | --- | --- | --- | --- |
| `GET /kpis` | viewer, owner | `from`, `to` (IST dates), `org_id?` | `[{key, label, available, unavailable_reason, value, unit, numerator, denominator, currency?, source_tables[], computed_at}]` | 422 range |
| `GET /kpis/{key}/series` | viewer, owner | `from`, `to`, `grain=day\|month`, `org_id?` | `{key, points:[{period, value, numerator, denominator}]}` | 404 key; 409 `not_available` |
| `GET /kpis/{key}/rows` | viewer, owner | `from`, `to`, `org_id?`, `part=numerator\|denominator`, `cursor` | `{items:[{table, id, org_id, org_name, at, value?}], next_cursor}`, the source rows | same |

### 3.2 AI usage and margin
| Method and path | Who | Request | Response |
| --- | --- | --- | --- |
| `GET /ai/usage` | viewer, owner | `from`, `to`, `group_by=feature\|model\|org\|provider\|prompt_version`, `org_id?` | `[{key, calls, input_tokens, output_tokens, cost_amount, currency, error_rate, blocked_count, latency_p50_ms, latency_p95_ms}]`. Sums and percentiles are computed in SQL (`numeric`, `percentile_cont`) |
| `GET /ai/evals` | viewer, owner | `suite?` | `[{suite, git_sha, run_at, score, pass_mark, passed, cases, cost_per_case, currency}]`, read from the S3 eval reports (§10, PR 12). `[]` if none |
| `GET /margin` | viewer, owner | `month` | `{month, fx_applied:false, rows:[{org_id, org_name, revenue:[{amount,currency}]\|null, ai_cost:{amount,currency:"USD"}, infra_alloc:{amount,currency:"USD"}, margin:[...]\|null, basis}]}`. `revenue` is null until Q2; `margin` is null when revenue is null or the currencies differ and no FX rule exists (Q3) |
| `GET /infra-costs` | viewer, owner | `month` | `{rows:[{service, amount, currency, counts_as_infra}], total_infra, fetched_at}` |

E0b's `/costs/*` and `/spend-caps` stay as they are; the AI usage screen links to them.

### 3.3 Events explorer and support view
| Method and path | Who | Request | Response | Errors |
| --- | --- | --- | --- | --- |
| `GET /events` | viewer, owner | `from`, `to` (required, ≤ 31 days), any of `org_id`, `rfq_id`, `po_id`, `actor` (exact, e.g. `agent:quote_draft`), `type_prefix`, `cursor` | `{items:[{id, created_at, org_id, org_name, created_by, source, type, subject_type, subject_id, rfq_id, po_id, request_id, payload(masked)}], next_cursor}` | 422 no filter and range > 1 day |
| `GET /orgs` | viewer, owner | `q` (name prefix or exact id), `kind?`, `status?`, `cursor` | `[{id, name, kind, status, is_test, created_at}]` | |
| `GET /orgs/{id}` | viewer, owner | | `{org(masked contacts), people_count, open_error_groups[], failed_jobs_open, approvals_pending, ai_cost_mtd, last_event_at}` | 404 |
| `GET /orgs/{id}/timeline` | viewer, owner | `cursor`, `type_prefix?` | the same shape as `/events`, scoped to the org | |
| `POST /orgs/{id}/suspend` | **owner** | `{reason: 3–200}` | org | 409 `not_supplier` (suppliers only in this story), 409 `already_suspended` |
| `POST /orgs/{id}/reinstate` | **owner** | `{reason}` | org | 409 |
| `POST /orgs/{id}/contacts/reveal` | **owner** | `{subject_type: "org"\|"person", subject_id, reason_code, note: 10–200}` | `{contacts:{phone, email, website}, expires_at}` | 403 viewer; 404 subject not in org; 429 more than 10 reveals per staff per day |

### 3.4 Agent outcomes and approvals
| Method and path | Who | Request | Response |
| --- | --- | --- | --- |
| `GET /outcomes` | viewer, owner | `from`, `to`, `agent?`, `org_id?` | `[{agent, prompt_id, prompt_version, decided, approved_as_is, edited, rejected, as_is_rate, median_fields_edited, median_time_to_decision_s}]` |
| `GET /outcomes/items` | viewer, owner | the same filters plus `decision`, `cursor` | `[{approval_id, org_id, org_name, agent, prompt_version, subject_type, subject_id, decision, fields_edited_count, decided_at}]`, with no draft content |
| `POST /approvals/{id}/flag-for-eval` | viewer, owner | `{note: ≤200}` | `{flagged:true}` writes an event only. qa-evals turns it into a consented, de-identified case under CLAUDE.md rule 10. No data is copied |
| `GET /approvals/stuck` | viewer, owner | `older_than_h` (default 24, Q13) | `[{approval_id, org_id, org_name, agent, subject_type, subject_id, requested_at, age_h}]`, read-only |

### 3.5 Issues: errors, logs, health, jobs
| Method and path | Who | Request | Response | Errors |
| --- | --- | --- | --- | --- |
| `GET /errors` | viewer, owner | `status?`, `kind?`, `org_id?`, `since?`, `cursor` | `[{id, kind, exception_type, location, route_or_job, status, occurrences_total, occurrences_24h, orgs_affected_24h, first_seen_at, last_seen_at, last_release}]` | |
| `GET /errors/{id}` | viewer, owner | | group + last 50 occurrences `[{request_id, org_id, org_name, actor, http_status, release, created_at}]` | 404 |
| `GET /errors/by-request/{request_id}` | viewer, owner | | `{group_id, occurrence}`; this is the "Reference" search | 404; 422 bad format |
| `POST /errors/{id}/resolve` / `ignore` / `reopen` | **owner** | `{note?: ≤200}` (`ignore` requires a note) | group | 409 bad transition |
| `GET /logs` | viewer, owner | `request_id` (regex `^[A-Za-z0-9\-:.]{8,80}$`), `at` (occurrence time) | `{lines:[{ts, service, level, logger, message(masked)}], truncated, window:{from,to}}` | 422 format; 429 (10 per staff per minute); 502 `log_query_failed`; 504 `log_query_timeout` (10 s) |
| `GET /health` | viewer, owner | | `{checked_at, items:[{component, status ∈ {ok,degraded,down,not_configured,unknown}, reason_code, facts:{…}}]}` (§3.6) | |
| `GET /jobs/schedules` | viewer, owner | | `[{job_type, schedule, last_started_at, last_finished_at, last_status}]` from `job.started`/`job.finished` events | |
| `GET /jobs/failed` | viewer, owner | `state?`, `queue?`, `org_id?`, `cursor` | `[failed_jobs row with payload masked]` | |
| `GET /jobs/failed/{id}` | viewer, owner | | row + linked error group + retry chain | 404 |
| `POST /jobs/failed/{id}/retry` | **owner** | `{reason: 3–200}` | row (`retried`) | 409 not `open`; 409 `job_type_not_retryable`; 502 `queue_error` |
| `POST /jobs/failed/{id}/discard` | **owner** | `{reason: 3–200}` | row (`discarded`) | 409 not `open` |

**Logs query (the only path to CloudWatch from the console):**
- The api runs Logs Insights only on `/orsyn/<env>/api` and `/orsyn/<env>/worker`, with a fixed query: `filter request_id = "<validated id>" | sort @timestamp asc | limit 200`. The window is `at ± 15 min`.
- The browser never sends free-text queries, so there is no ad-hoc grepping of personal data and no query injection.
- Lines are masked again before return. An "Open in CloudWatch" link is shown as a fallback for owners.

**Retry semantics:**
- Retry sends a **new** SQS message to the source queue. It carries the same payload and `idempotency_key`, plus an attribute `retry_of=<failed_job_id>`. The row moves to `retried`.
- If the job later succeeds, the worker marks the row `succeeded_after_retry`. If it fails again, the drain creates a new row with `retry_of` set.
- Job handlers must be idempotent on `idempotency_key` (contract for every job story). A job type is retryable only if its handler declares `retryable = True`.
- Jobs that send to a customer (email, WhatsApp) re-check that the approval exists and that the message has not already been sent; already sent → no-op. **A retry never creates new outbound content and never bypasses `approvals`.**

### 3.6 Health checks (on request, cached 30 s, each with a 2 s timeout)
| Component | Check | ok / degraded / down |
| --- | --- | --- |
| Database | `SELECT 1` latency; RDS `CPUUtilization`, `FreeStorageSpace`, `DatabaseConnections` via `GetMetricData` (last 15 min) | down if the query fails; degraded if latency > 200 ms, CPU > 80% or free storage < 20% |
| Services | `ecs:DescribeServices` for api, web, worker: running vs desired, task definition image tag (git SHA), last deployment state | down if running = 0; degraded if running < desired |
| Queues | `sqs:GetQueueAttributes` on each queue and DLQ: visible, in-flight; plus `failed_jobs` open count | degraded if DLQ visible > 0 for 15 min (drain broken) or open failed jobs > 0 |
| Bedrock, Sarvam | passive: `model_calls` in the last 15 min (error rate, `unavailable` count) + E0b provider status + last test | E0b's `Failing` rule; `not_configured` if Missing |
| Email | provider-specific (Q6). If SES: `ses:GetAccount` (sending enabled, 24 h send quota used) + bounce rate from `outbound_messages` once it exists | down if sending is disabled |
| WhatsApp | passive: last successful send and last webhook received (from events) + E0b credential status | degraded if no webhook in 24 h while sends happened; `not_configured` if Missing |
| PostHog | configuration only (key present or not); no call | `not_configured` or ok |

### 3.7 Safe admin actions (all owner-only, reason required, each one event)
Resolve, ignore or reopen an error; retry or discard a failed job; suspend or reinstate a supplier; reveal a contact; flag an approval for eval. In phase C, **resend an email** (`POST /messages/{id}/resend`, owner): it re-queues delivery of the exact stored, already-approved message to the same recipient, only for `status ∈ {failed, bounced}` and within 30 days, through the idempotent send job. **None** of them edit amounts, quotes, POs, documents, rules or prices, approve anything, or delete a business row.

---

## 4. Events

Same shape as E0b/E0c, plus the new `rfq_id` and `po_id` columns. Sources: `admin_ui`, `job`, `system`. **No payload contains contacts, message text, prompts or key material** (tested).

| Type | Actor | Source | Payload |
| --- | --- | --- | --- |
| `admin.viewed` (E0b) | person | admin_ui | `{path, filters}`, now also for `/events`, `/orgs/*`, `/logs`, `/kpis/*/rows`, `/outcomes/items`; throttled as in E0b, except `/logs`, which is never throttled and records `request_id` |
| `error_group.created` | `system:error_capture` | system | `{group_id, kind, exception_type, location, release}` (drives the "new error" alert) |
| `error_group.resolved` / `.ignored` / `.reopened` | person, or `system:error_capture` for auto-reopen | admin_ui / system | `{group_id, note?, release}` |
| `failed_job.ingested` | `system:dlq_drain` | job | `{failed_job_id, queue, job_type, receive_count}` |
| `failed_job.retried` / `.discarded` | person | admin_ui | `{failed_job_id, reason, new_message_id?}` |
| `failed_job.succeeded_after_retry` | `system:worker` | job | `{failed_job_id}` |
| `org.suspended` / `.reinstated` | person | admin_ui | `{reason}` (`subject_type=org`) |
| `staff.contact_revealed` | person | admin_ui | `{subject_type, subject_id, reason_code, note, expires_at}`; never the contact itself |
| `approval.flagged_for_eval` | person | admin_ui | `{approval_id, agent, prompt_version, note}` |
| `message.resend_requested` (phase C) | person | admin_ui | `{message_id, approval_id, reason}` |
| `job.started` / `job.finished` | `system:<job>` | job | `{job_type, status, duration_ms, items}`, for scheduled jobs only, including `infra_cost_fetch` and `error_occurrence_prune` |
| `error_occurrence.pruned` | `system:error_occurrence_prune` | job | `{deleted_count, older_than}` |

---

## 5. AI agents

**No agent, prompt or gateway behaviour changes. No model is called by the console.** The outcomes page reads `approvals` and is the online quality signal for every agent. "Flag for eval" only marks a case for qa-evals; ai-engineer adds it to `evals/<agent>/cases.jsonl` after consent and de-identification (CLAUDE.md rule 10). The confidence field and approval point of each agent are unchanged and owned by their stories. The eval *reports* that CI already writes are uploaded to S3 so the AI usage page can show the latest score per suite (§10, PR 12). No prompt file is added; the cost-logging feature prefix `ops_` is reserved in case one is ever needed.

---

## 6. Rules

None from `packages/rules` are read by default. KPI windows (7-day maturity, 30-day activation, 90-day repeat, 24 h stuck) are product definitions, not export or scheme rules. They live as named constants in `app/ops/kpis.py`, are listed on each KPI card, and are confirmed by the founder (Q13).

Conditional: if Q3 chooses FX conversion for margin, rules-curator adds `fx.usd_inr.monthly` (FBIL/RBI reference rate, a source URL, `checked_on` per month), and the margin code reads it. That PR gets the `rules-change` label. No requirement goes into any prompt.

---

## 7. Screens

`docs/screens.md` does not exist, so frontend builds to this section and `frontend.md`; the founders add these screens to `screens.md` (Q16). The screens live in the E0b route group `app/(admin)/admin/...`, with the same shell, environment label and formats (IST times, `US$`/`₹` with en-IN grouping, IBM Plex Mono for ids, amounts and SHAs). Every number comes from the server; nothing is summed in the browser. Status is coloured text (ok, warn, bad, muted). Desktop-first at 1440px, usable at 390px.

**Side panel after this story:** Overview · AI usage · Outcomes · Events · Customers · Errors · Jobs · Health, then E0b's Providers · Routing · Spend caps · Costs · Audit.

| Screen | Holds | Empty | Loading | Error |
| --- | --- | --- | --- | --- |
| **Overview** `/admin` | IST date range picker, customer filter, "include test orgs" off. KPI cards (§1.3): value, numerator/denominator, small SVG trend, "Rows" link, definition footnote. Unavailable cards show "Available after M1" / "after M2" / "Revenue model not set" in muted | "No activity in this range." | skeleton cards | "Couldn't load KPIs." + Retry, per card |
| **KPI rows** `/admin/kpis/[key]` | Definition, then the numerator/denominator tabs as a table of source rows, each linking to the events explorer filtered to that row | "No rows." | skeleton rows | error + Retry |
| **AI usage** `/admin/ai` | Range picker; group-by tabs (feature, model, customer, provider, prompt version); table: calls, tokens in/out, cost, error rate, p50/p95 latency, blocked. An eval card per suite: score vs pass mark, SHA, cost per case. Margin table per customer for the month: revenue, AI cost, infra share, margin, basis. Links to E0b Costs and Spend caps | "No model calls in this range." Evals: "No eval reports uploaded yet." Margin: "Revenue model not set." | skeleton | error + Retry |
| **Outcomes** `/admin/outcomes` | Per agent and prompt version: decided, as-is, edited, rejected, as-is rate (ok ≥ 70%, warn below, Q13), median fields edited. Drill-down list with "Flag for eval". Second tab: **Stuck approvals** (> 24 h) | "No decisions yet." / "Nothing waiting more than 24 hours." | skeleton | error + Retry |
| **Events** `/admin/events` | Filters: date range (required), org, RFQ id, PO id, actor, type prefix. Table: time, org, actor, type, subject, request id (links to logs), masked payload summary; row expands to the full masked payload | "No events match these filters." | skeleton | error + Retry; 422 shows "Add a filter or narrow the range to one day." |
| **Customers** `/admin/customers` and `/admin/customers/[id]` | Search by name or id. Detail: org card (kind, status, test flag, created, masked contacts, owner-only **Reveal** with reason dialog, countdown to re-mask), counts (open errors, failed jobs, pending approvals, AI cost MTD), timeline (paginated events), owner-only **Suspend / Reinstate** for suppliers with a reason | "No customers found." / "No events for this customer yet." | skeleton | error + Retry; action errors inline |
| **Errors** `/admin/errors` and `/admin/errors/[id]` | "Find by reference" box (request id). List: status, exception, location, route/job, count 24 h, orgs affected, last seen, release. Detail: occurrences table; each row has **View log lines** (inline panel, mono, masked) and links to the customer; owner actions Resolve / Ignore (note) / Reopen | "No open errors." in ok colour | skeleton; log panel "Fetching log lines…" | list: error + Retry; logs: "Log lines are not available (older than 30 days or query failed)." |
| **Jobs** `/admin/jobs` | Schedules table (last run, status). Failed jobs: queue, type, org, first failed, receive count, state, linked error. Detail: masked payload, retry chain; owner **Retry** / **Discard** with a reason and a confirm dialog that names the job type | "No failed jobs." in ok colour | skeleton | error + Retry; 409 shown inline |
| **Health** `/admin/health` | One row per component: status, reason, key facts (latency, depth, SHA, running/desired), checked at. Auto-refresh every 60 s while the tab is visible | n/a (always has rows) | skeleton rows | "Couldn't run health checks." + Retry; an individual check that fails shows `unknown` in muted |

**Customer-facing change (web, small):** the existing `error.tsx` shows "Reference: `<request id>`" when the failed API response carried `X-Request-Id`. PostHog init lives in the buyer/supplier layouts only.

Accessibility as E0b: real buttons, labelled inputs, 44px targets, 4.5:1 contrast.

---

## 8. Tests and evals (qa-evals; api tests in `services/api/tests/`, web in `apps/web/tests/`)

### 8.1 One test per proposed "Done when" clause
| Clause | Test |
| --- | --- |
| (a) KPIs with rows | `test_kpis_match_fixture_formulas`: a fixture set of orgs (including one `is_test`), RFQs, invites, quote versions, awards and PO lines across an IST month boundary (18:30 UTC). Each KPI's value, numerator and denominator equal hand-computed `Decimal`/int values written in the test. Test orgs are excluded. `test_kpi_rows_reconcile`: the `rows` count equals the numerator/denominator for every KPI. `test_kpi_unavailable_before_tables`: with M1/M2 tables absent, `available=false` and a reason |
| (b) AI usage and margin | `test_ai_usage_groupings`: sums, error rate and p50/p95 equal fixture values per group. `test_margin_never_mixes_currencies`: INR revenue + USD cost → `margin=null` without an FX rule. `test_infra_alloc_excludes_marketplace`: rows with `counts_as_infra=false` are not allocated. `test_eval_reports_read_from_s3` (stubbed S3) |
| (c) events explorer + reveal | `test_events_filters` (org, rfq_id, po_id, actor, type prefix, range cap). `test_events_payload_masked`. `test_reveal_owner_only_with_reason_and_event`: viewer → 403; owner without reason → 422; owner → contacts + `staff.contact_revealed` with no contact in the payload; after 15 minutes (frozen time) the org card is masked again; the 11th reveal in a day → 429 |
| (d) outcomes | `test_outcome_mapping`: approved/edited/rejected per the §2.6 mapping, per agent and prompt version. `test_flag_for_eval_writes_event_only` (no new rows besides the event) |
| (e) errors within a minute + logs | `test_unhandled_exception_creates_group_and_occurrence`: one group, one occurrence with `request_id`, a second identical error increments the count, no exception message in any column. `test_job_failure_captured`. `test_resolved_group_reopens_on_new_release`. `test_logs_query_is_fixed_and_validated`: stubbed CloudWatch; only the two log groups; the query contains only the validated id; an injection-shaped id → 422; returned lines are masked |
| (f) health | `test_health_components`: each component with stubbed AWS/DB returns ok/degraded/down/not_configured per §3.6; a check that times out → `unknown`, not a 500 |
| (g) failed jobs | `test_dlq_drain_ingests_once` (same message id twice → one row). `test_retry_sends_same_payload_with_retry_of_and_event`. `test_discard_is_state_change_not_delete`. `test_viewer_cannot_retry_or_discard`. `test_non_retryable_job_type_409` |
| (h) alerts | infra: plan or `synth` assertion that each §8.4 alarm exists, targets the right SNS topic and has the stated threshold. api: `test_alert_log_lines_shape` for `orsyn.error`, `orsyn.error.new_group`, `orsyn.jobs.failed` (the metric filters depend on the JSON field names) |
| (i) PostHog | web `analytics.test.ts`: no init without a key; no init on the admin host; `track()` rejects unknown events and unknown properties at type level and at runtime; `before_send` strips query strings; the init config has `autocapture:false`, `maskAllInputs:true`, `maskTextSelector:"*"`. api `test_posthog_noop_without_key`, `test_server_events_allowlisted`, `test_server_event_names_equal_event_types` |
| (j) audit, no money, no deletion | `test_every_ops_mutation_writes_one_event` (parametrised over all mutating routes). `test_ops_routes_touch_no_money_tables`: a static check that `app/ops/**` imports no write repository for quotes, POs, PO lines, documents, rules or prices, and that no `DELETE` exists outside `error_occurrence_prune` |

### 8.2 Negative tests (always)
- **Masking before award:**
  - an RFQ with an unawarded supplier: the events explorer, org timeline, failed-job payload, error rows, log viewer and KPI rows contain no phone, email or website pattern (regex scan of every response);
  - a write-time test that `events.payload` and `failed_jobs.payload` reject values matching contact patterns;
  - the staff reveal is the only path that returns a contact.
- **`org_id` isolation:**
  - every ops repository requires `PlatformScope`, and a customer-context call raises;
  - `/admin/v1/*` on the customer host → 404;
  - a customer credential on admin routes → 401;
  - the `org_id` filter returns only that org's rows (two-org fixture for every list endpoint);
  - `error_occurrences.org_id` and `failed_jobs.org_id` come from the job or request context, never from client input.
- **Approval required:**
  - retrying a send job whose approval is missing → handler no-op plus an error event;
  - retrying an already-sent message → no second send (idempotency);
  - the resend action (phase C) refuses messages without `approval_id`;
  - no ops route can change an `approvals.status` (static plus API check).
- **PostHog privacy:** a property-level scan of every server `track()` call site in tests shows only allow-listed keys; a replay config snapshot test.
- **Auth and transport:** inherit E0b's tests for new routes (CSRF header, Origin, Host, OpenAPI absence) through the same parametrised suite.

### 8.3 Evals
No agent or prompt changes, so no agent eval suite. `_smoke` stays at 100% with cost 0. The S3 upload of eval reports is tested in CI by a dry-run mode (no AWS).

### 8.4 Alerts (infra builds them; listed here so they are tested)
| Alert | Source | Threshold (founder confirms, Q5) | Topic |
| --- | --- | --- | --- |
| Site down | Route 53 health check on `https://<app>/health` | 3 failures in a row (≈ 1.5 min) | critical |
| API 5xx spike | ALB `HTTPCode_Target_5XX_Count` | > 10 in 5 min | critical |
| Error spike | metric filter on `orsyn.error` | > 20 in 5 min | critical |
| New error group | metric filter on `orsyn.error.new_group` | ≥ 1 | info |
| Failed job | metric filter on `orsyn.jobs.failed` | ≥ 1 in 5 min | info |
| DLQ not draining | SQS DLQ `ApproximateNumberOfMessagesVisible` | > 0 for 15 min | critical |
| Provider down | E0b `orsyn.ai.provider_unavailable` | ≥ 1 | critical |
| Spend cap hit / 80% | E0b `orsyn.ai.spend_alert` | ≥ 1 | critical (block) / info (80%) |
| AI cost spike | metric filter summing `cost_amount` from `orsyn.ai.cost` | > US$5 in 1 h (prod) | critical |
| ECS tasks below desired | Container Insights is **not** enabled (cost); uses the ECS service `RunningTaskCount` via a scheduled check in the health job | running < desired for 10 min | critical |
| RDS storage / CPU | `FreeStorageSpace` < 20%, `CPUUtilization` > 80% for 15 min | | critical |
| AWS Budget (E0b) | AWS Budgets | as E0b | email |
| Staff contact reveal | `staff.contact_revealed` log line | ≥ 1 | info |

Channel: two SNS topics per environment, `orsyn-<env>-ops-critical` and `orsyn-<env>-ops-info`, with email subscriptions to both founders. Dev sends info only. Slack through AWS Chatbot (free, no key in our app) is optional if the founders use Slack (Q5). SMS is not proposed: Indian SMS needs DLT sender registration.

---

## 9. Cost

**Model calls per user action: 0** for every console read and action. No gateway calls, so there is no cost-logging feature name; the prefix `ops_` is reserved.

**Monthly, prod** (list prices; infra confirms in the PR):

| Item | Estimate |
| --- | --- |
| CloudWatch alarms (~13 × US$0.10) | US$1.30 |
| Custom metrics from metric filters (~6 × US$0.30) | US$1.80 |
| Logs Insights queries (≈ 30-minute window on two groups, MBs scanned, a few hundred per month) | < US$0.50 |
| `GetMetricData` for health (cached 30 s, only when the page is open) | < US$0.20 |
| Cost Explorer API (1 call per day, US$0.01 each) | US$0.30 |
| Route 53 health check (HTTPS, AWS endpoint) | ≈ US$1–2 |
| S3 eval reports | < US$0.05 |
| SNS email | US$0 (free tier) |
| PostHog EU Cloud, free tier, billing limit set | US$0 |
| **Prod total** | **≈ US$6 (≈ ₹510 at ₹85/US$)** |

Dev: about US$3 (no Route 53 check, fewer alarms). **Total change ≈ US$9/month (≈ ₹765) for dev plus prod.** For comparison (not chosen): Sentry Team from US$26/mo; self-hosted Metabase ≈ US$35–45/mo; Metabase Cloud ≈ US$100/mo. CloudWatch log ingestion and storage already exist; this story sets **retention to 30 days in prod and 7 in dev**, which bounds that cost.

PostHog risk: if traffic passes the free tier, ingestion stops at the billing limit and the app is unaffected; the KPIs never depend on PostHog.

---

## 10. PR split

**Prerequisites:** E0 merged; E0c (DB baseline); E0b PRs 1–3 and 5 (tables, admin auth, gateway core, admin API) for every PR here; E0b PRs 7–8 (admin web) before the web PRs. Phase B waits for the M1 tables in §2.6; phase C waits for M2 and Q2.

**Suggestion (Q1):** ship phase A as this story; phases B and C become small follow-up stories under M1 and M2 so they are planned with those tables.

### Phase A — operate without servers (can start once E0b lands)
| # | PR | Builder(s) | ~Lines | Labels |
| --- | --- | --- | --- | --- |
| 1 | Migration (reversible): `error_groups`, `error_occurrences`, `failed_jobs`, `infra_costs_daily`; `orgs.status`/`is_test`; `events.rfq_id`/`po_id` + indexes; event writer helper args; repositories with `PlatformScope`; tests | backend, qa-evals | ~360 | needs-founder, security-review |
| 2 | Request-id middleware, JSON logging with the masking filter, exception handler + job runner wrapper, fingerprinting, best-effort capture, `orsyn.error*` log lines, prune job; tests | backend, qa-evals | ~360 | security-review |
| 3 | Ops API (issues): errors list/detail/by-request/resolve/ignore/reopen, Logs Insights client (fixed query, stubbed), health checks; tests | backend, qa-evals | ~390 | security-review |
| 4 | Jobs: DLQ drain consumer → `failed_jobs`, retry/discard, `retryable` and idempotency contract in the job base class, `job.started/finished`, schedules endpoint; tests | backend, qa-evals | ~380 | needs-founder, security-review |
| 5 | Events explorer, orgs search, support summary and timeline, suspend/reinstate, contact reveal; tests | backend, qa-evals | ~390 | needs-founder, security-review |
| 6 | AI usage aggregates, eval reports reader (S3), Cost Explorer fetch job → `infra_costs_daily`, `/infra-costs`, `/margin` (revenue null); tests | backend, qa-evals | ~370 | security-review |
| 7 | Web: Errors (+ log panel, find by reference), Jobs, Health; customer `error.tsx` reference line; tests | frontend, qa-evals | ~390 | |
| 8 | Web: Events explorer, Customers list and detail, reveal and suspend dialogs; tests | frontend, qa-evals | ~390 | security-review |
| 9 | Web: AI usage (usage, evals, margin) and the Overview shell with unavailable KPI cards; side panel; tests | frontend, qa-evals | ~350 | |
| 10 | PostHog web: typed tracking plan, init config, admin-host guard, CSP, layouts, client events; tests | frontend, qa-evals | ~300 | security-review |
| 11 | PostHog api: `app/analytics/` wrapper (no-op without key), allow-listed server events after commit, new dep `posthog` (justified); tests | backend, qa-evals | ~220 | security-review |
| 12 | Infra: IAM additions (below), log retention, SNS topics, metric filters and alarms (§8.4), Route 53 health check, S3 `orsyn-<env>-ops` bucket for eval reports + CI upload step via OIDC, PostHog key as plain task env (public ingestion key, not a secret), cost note | infra | ~350 | needs-founder, security-review |

**PR 12 IAM additions to the api task role (read-only except where noted):**
- `logs:StartQuery`, `logs:GetQueryResults` on the two log groups only.
- `cloudwatch:GetMetricData` (no resource scoping exists for it).
- `sqs:GetQueueAttributes` on our queues; `sqs:SendMessage` to source queues (already held); worker role: `ReceiveMessage`/`DeleteMessage` on DLQs.
- `ecs:DescribeServices` on the cluster's services.
- `ce:GetCostAndUsage`.
- `ses:GetAccount` if SES (Q6).
- `s3:GetObject`/`ListBucket` on the ops bucket prefix `evals/`.
- CI deploy role: `s3:PutObject` on that prefix only.

The ops reads run under the api task role in the same service; a separate admin service is Q14.

### Phase B — after M1 tables (follow-up story)
| # | PR | Builder(s) | ~Lines | Labels |
| --- | --- | --- | --- | --- |
| 13 | KPI registry + M1 KPIs (§1.3) with series and rows; AI and all-in cost per RFQ; tests with hand-computed fixtures | backend, qa-evals | ~390 | |
| 14 | Outcomes and stuck approvals API, flag for eval; tests | backend, qa-evals | ~250 | security-review (reads approvals) |
| 15 | Web: Overview KPI cards live, KPI rows page, Outcomes page; tests | frontend, qa-evals | ~350 | |

### Phase C — after M2 and Q2 (follow-up story)
| # | PR | Builder(s) | ~Lines | Labels |
| --- | --- | --- | --- | --- |
| 16 | Award rate, GMV, revenue and take rate, margin with revenue (and FX if Q3 says so, with the rules-curator rule); tests | backend, rules-curator (if FX), qa-evals | ~320 | needs-founder (revenue definition), rules-change (if FX) |
| 17 | Resend email action (after the email story), web button; tests | backend, frontend, qa-evals | ~220 | needs-founder, security-review |

**Order:** 1 → 2 → 3; 4 after 2; 5 after 1; 6 after 1. Web 7 needs 3 and 4; 8 needs 5; 9 needs 6. 10 and 11 are independent of the rest (after E0b web); 12 is reviewed in parallel and merges before prod use. security-reviewer is required on every PR labelled security-review; product-reviewer checks each phase at its end.

**File ownership** (no overlap): backend `app/ops/**`, `app/analytics/**`, `app/jobs/**` base and drain, `app/observability/**` (middleware, logging, capture), migrations; frontend `apps/web/app/(admin)/admin/{ai,outcomes,events,customers,errors,jobs,health,kpis}/**`, `apps/web/lib/analytics/**`, layouts and CSP; infra `infra/**`, `.github/workflows/ci.yml` (eval upload step); qa-evals tests. backend adds the `posthog` dependency to `pyproject.toml`; frontend adds `posthog-js` to `apps/web/package.json`.

Phase A total ≈ 4,250 lines over 12 PRs; B ≈ 990; C ≈ 540.

---

## 11. Flags

- **needs-founder: yes.**
  - **Migrations:** four new tables, plus new columns on `orgs` and `events`.
  - **Approval paths:** job retry and email resend re-trigger sends that were already approved, so idempotency and approval re-checks are part of the design.
  - **Data deletion:** the 30-day `error_occurrences` prune and the log retention change.
  - **Spend:** CloudWatch, Route 53 and the PostHog billing limit.
  - **Revenue definition:** for phase C.
- **security-review: yes.**
  - **Isolation:** staff cross-org reads through `PlatformScope`.
  - **Masking:** the staff reveal rule, payload write-time checks, log masking and the log viewer.
  - **Auth:** reuse of E0b admin auth on new routes.
  - **IAM:** Logs, CloudWatch, SQS, ECS and Cost Explorer reads on the customer-facing api role, plus the CI S3 upload.
  - **Third-party data flow:** PostHog EU, replay masking and CSP.
  - **Query construction:** Logs Insights queries built from user input.
- `rules-change`: only if Q3 adds an FX rule (phase C).
- Milestone label: M1 for phase A (Q1).

---

## 12. Open questions

1. **Story key, "Done when" and split.** Is `E0d` right? Confirm the proposed "Done when". Should phases B and C be separate follow-up stories under M1 and M2 (recommended)?
2. **Business model.** What is revenue?
   - (a) commission % on GMV, paid by buyer or supplier;
   - (b) buyer subscription;
   - (c) Orsyn as merchant of record, earning the margin between buy and sell;
   - (d) paid supplier services (export roadmap, benefits).

   Who is invoiced, and in which system? Revenue and take rate stay "not set" until answered.
3. **FX for margin.** AI cost is in USD; revenue is likely in INR. Options:
   - show them side by side (default);
   - add an FBIL/RBI monthly reference rate as a rule with a source and checked date, and compute one margin figure.
4. **Errors.** Accept CloudWatch-only plus `error_groups`, with no browser errors for now? Or add Sentry Team (EU region, from US$26/mo) now?
5. **Alerts.** Email only, or also Slack via AWS Chatbot (do you use Slack)? Confirm the thresholds in §8.4, especially the AI cost spike of US$5 per hour in prod.
6. **Email and WhatsApp providers.** SES or another email provider? Meta WhatsApp Cloud API direct or a BSP? This decides the health checks and IAM.
7. **PostHog.**
   - Is EU (Frankfurt) acceptable for pseudonymous product analytics?
   - Should there be a notice-only approach in the privacy terms, or an opt-in banner under the DPDP Act (counsel)?
   - What replay sample rate (suggest 20% of logged-in sessions; supplier PWA on mobile data could be excluded)?
   - Who owns the PostHog org and sets the billing limit?
8. **Staff contact reveal rule (§1.4).** Approve it: owner only, reason code plus note, 15 minutes, 10 per day, and an email to the other owners. Should viewers also be able to request a reveal?
9. **Supplier suspension.** What does it do beyond hiding the supplier from matching and new invites? What happens to open quotes? Who tells the supplier, and how?
10. **Staff roles.** Are viewer/owner enough, or should ops staff (later) get a third role that can retry jobs but not reveal contacts?
11. **Restart or redeploy from the console.** Not built (ECS self-heals; deploys go through CI). Is that OK?
12. **Infra allocation and test orgs.** Should infra cost be allocated by share of RFQs plus quotes (proposed), split equally, or by AI-cost share? Who marks orgs as test (CLI, proposed)?
13. **KPI windows.** Confirm 7-day RFQ maturity, 30-day supplier activation, 90-day buyer repeat, 24 h stuck approval, and a 70% as-is target.
14. **Ops reads in the customer-facing api.** Is the same service and task role acceptable for Phase 1 (simplest, US$0)? Or should the admin api run as a separate ECS service with its own read-only role (≈ US$9–10/mo for 0.25 vCPU)?
15. **E0c contract.** If E0c has not merged, should it carry `orgs.status`, `orgs.is_test`, `events.rfq_id` and `events.po_id`, with this story's migration dropping them?
16. **`docs/screens.md`.** Who adds these admin screens? Do you want a sketch of Overview and Errors before PR 7?
17. **Metabase.** Agree to defer it (§1.7) until ad-hoc questions are weekly, and then only on masked reporting views?
