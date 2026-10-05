# AST — In-app assistant ("Help") for buyers and suppliers

Status: draft, waiting for founder OK. Author: architect. Date: 2026-10-05. Story key **AST is provisional** (Q1).

Inputs read: `CLAUDE.md`, `KICKOFF.md`, `.claude/agents/*`, `docs/plans/E0-repo-ci.md`, `docs/plans/E0b-admin-provider-keys.md`. `docs/build-plan.md`, `docs/screens.md` and `docs/architecture.md` do not exist yet, and there is no application code. This plan therefore depends on contracts that later stories create (customer login, `approvals`, masking serializers, RFQ, quote, order and roadmap modules). §10 lists those dependencies.

The founder's ask, verbatim: "an assistant on top of this for both buyer side and supplier with access to their own data to answer and perform events, also maybe its own browser to guide or assist suppliers or buyers do. Say for example like tutorial or some help or apply something etc."

---

## 1. Goal

Give each signed-in buyer and supplier a panel called **Help**. It answers questions from their own data, our help articles and the rules table, and it cites its sources. It guides the user inside Orsyn by moving to a screen, pointing at a control or filling in a form. It can draft changes that the user confirms. It never sends, awards, pays or deletes anything by itself.

### 1.1 Three capability tiers and the recommended order

| Tier | What it is | Recommendation | Milestone |
| --- | --- | --- | --- |
| **1. Help and answers** (story **AST-1**) | "How do I…", "What's the status of my RFQ?", "Why is this step mandatory?" Answers are grounded in the user's data (read through our own API as that user), help articles and `packages/rules`, with citations. Read-only. | **Build first.** | **After M1 ships**: RFQs, quotes, masking and the `approvals` table must exist first. Label M2, built alongside M2 work. |
| **2. In-app guidance and drafts** (story **AST-2**) | A typed UI-action protocol (`navigate`, `highlight`, `tour`, `prefill`) that the frontend runs against a fixed registry. State changes become an **approvals** record with a Confirm card. | **Build second.** | **After M2** (award and PO exist, and the never-list is enforceable against real endpoints). Label M3. |
| **2b. WhatsApp surface** (story **AST-WA**) | The same assistant core over WhatsApp. Text and voice (Sarvam) for read-only answers. Every action becomes a deep link into the PWA to confirm. | Third. It needs the WhatsApp webhook story. | With or after M3. |
| **3. Acting on external portals** (DGFT, GST, ICEGATE) via a browser agent | Computer use on government sites | **Do not build in Phase 1.** Build **portal packs** instead (§5.6): a filled checklist, documents and a step-by-step walkthrough; the user submits on the portal. | Portal packs come with M4 (first export order). |

This plan designs AST-1 and AST-2 in full, and AST-WA and tier 3 to decision level only.

### 1.2 Proposed "Done when" (`docs/build-plan.md` does not exist; the founder must confirm, Q1)

> **AST-1 Done when:**
> (a) a signed-in buyer or supplier can ask, in English or Hindi, how to use Orsyn, about their own RFQs, quotes, orders or roadmap, or why a rule applies, and every fact in the answer cites a help article, a record of their own organisation, or a rule with its source and checked date;
> (b) every figure in an answer is rendered from a server value with a link to its source, and the model writes no money;
> (c) the assistant reads data only through our own API as the signed-in user; another organisation's data and masked contacts never appear in answers, prompts, stored messages or logs;
> (d) every model call is logged with org and feature, and when the org's spend cap is reached or the provider is down, Help falls back to article search with no model call;
> (e) only the person who had a conversation can see it; they can delete it, and it is purged after the retention period.
>
> **AST-2 Done when:**
> (a) the assistant can only navigate to, highlight on, tour or prefill screens and forms listed in the registry, and the app ignores any other action;
> (b) a prefilled form is never submitted automatically; the user's own Save or Submit is the action, and outbound steps still go through approvals;
> (c) a state change the assistant proposes appears as a Confirm card backed by an `approvals` record, and it runs only after the user confirms, with the user's permissions at that moment;
> (d) actions on the never-list are refused, and evals show zero unapproved actions.

### 1.3 How each non-negotiable is met

| Non-negotiable | How this design meets it |
| --- | --- |
| **Agents propose, people approve** | The model returns typed proposals only. Prefill fills a form in the browser and the user submits it. Other state changes become an `approvals` row (`kind = assistant_action`) that runs only when the user presses Confirm. Code holds an allow-list of draftable actions and a never-list (§5.4). The tool client can only issue `GET` requests. |
| **Tenant isolation** | Tools call **our own HTTP API in-process with the user's own credential**: same auth dependency, same `org_id` scoping, same serializers. There are no raw DB queries and no service-layer shortcuts. Conversations are scoped by `org_id` **and** `user_id`. Nothing is cached across requests. Isolation tests are in §8. |
| **Contacts hidden until award** | The assistant sees only what the API serializer returns, so masked fields are already masked before they reach the prompt. An output filter also blocks phone and email patterns that do not belong to the user's own record (§5.5). Contact fields are on the never-list for prefill and proposals. |
| **Numbers in code** | Tool results carry figures with `source_ref`. The model may only place a figure by reference (`{"type":"figure","ref":"f3"}`), and code renders the value and its link. The validator rejects any answer text containing an amount or currency that was not inserted by reference. Price fields can be prefilled only with a number the user typed verbatim in this conversation; totals and taxes are never prefilled. |
| **Every number traces to its source** | Every figure block renders with a link to its quote version, PO line, document line or rule. |
| **Rules from `packages/rules` only** | The `rules_for` tool returns rule rows (id, title, body, mandatory, source, `checked_on`). The answer prompt says to explain only what a returned rule says. The validator drops a "mandatory/required" claim unless a cited rule has `mandatory = true`. With no rule, the answer is "I don't have a rule for that" plus a link to ask Orsyn. No requirement text sits in any prompt. |
| **One gateway, cost logged** | Every call goes through `gateway.py` with features `assistant_route`, `assistant_answer` and later `assistant_translate` and `assistant_voice`. E0b per-org spend caps apply. When a cap blocks, Help falls back to zero-cost article search. |
| **Prompt injection** | Tool results, help articles, supplier and buyer messages and document text are wrapped as delimited data. The real defence is structural, not the prompt: read-only tools, a fixed allow-list, no URL-fetching tool, typed outputs, and a person confirming every change (§5.5). |
| **Never sold / ranking** | The assistant has no tool that changes match ranking or placement. It explains matches only as the matching module returns them, and it cannot reorder them. |
| **Languages** | English and Hindi in AST-1 (Claude answers in the user's language; Hindi is evaluated). Other Indian languages and voice go through Sarvam in AST-WA. |

### 1.4 Deliberately not building

- **Any browser agent on external sites (tier 3)**, or any storage of portal credentials, OTPs or DSCs.
- Streaming responses (SSE). The first version is request/response with a "Looking…" state; streaming can come later if p95 latency hurts.
- Embeddings or a vector index for help articles. Postgres full-text search over about 50 articles is enough; pgvector can come when the corpus grows.
- Long-term memory across conversations, and user-level personalisation.
- Org admins reading members' conversations.
- The assistant calling other agents (`quote_draft`, `rfq_from_drawing`). It navigates the user to the screen where they press that agent's existing button, which avoids hidden chained spend.
- Voice and WhatsApp in AST-1 and AST-2 (they come in AST-WA).
- A floating chat bubble, avatar or persona.

---

## 2. Ontology impact

Every new table has `id` (uuid), `org_id`, `created_at` (UTC) and `created_by` (`person:<uuid>`, `agent:assistant` or `system:<component>`), the E0b actor convention. The assistant creates no documents or PO lines, so the document-line → PO-line link does not apply. When it **cites** a document line or PO line, the citation stores that line's id.

### 2.1 `assistant_conversations` (AST-1)
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid FK orgs | the user's org |
| `user_id` | uuid FK users | **only this person can read it** |
| `surface` | text check in (`web`, `pwa`, `whatsapp`) | |
| `locale` | text check in (`en`, `hi`) | more locales come with AST-WA |
| `title` | text null | first 60 characters of the first question, after redaction |
| `last_activity_at` | timestamptz | |
| `purge_after` | timestamptz | `last_activity_at` + retention (Q4, default 90 days); recomputed on each turn |
| `deleted_at` | timestamptz null | set on user delete; messages are hard-deleted at the same moment |
| `created_at`, `created_by` | | `created_by` = `person:<user_id>` |

Index: (`org_id`, `user_id`, `last_activity_at desc`).

### 2.2 `assistant_messages` (AST-1)
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | same as the conversation; checked by a composite FK (`conversation_id`, `org_id`) |
| `conversation_id` | uuid FK | |
| `role` | text check in (`user`, `assistant`) | tool results are **not stored** |
| `content` | jsonb | user: `{text}` after redaction. Assistant: the validated block list (§5.2) with `figure` and `citation` refs, **not** the rendered values |
| `citations` | jsonb | `[{kind: help_article\|record\|rule, ref, label}]`. Record refs are ids only (`rfq:<uuid>`, `quote_version:<uuid>`, `po_line:<uuid>`, `rule:<id>@<checked_on>`) |
| `ui_actions` | jsonb | AST-2: the validated actions emitted, each with an `id` |
| `approval_ids` | uuid[] | AST-2: the proposals created by this turn |
| `intent` | text | the router's intent enum |
| `model_call_ids` | uuid[] | links to E0b `model_calls` for cost |
| `prompt_versions` | jsonb | `{assistant_router: 1, assistant_answer: 1}` |
| `confidence` | numeric(3,2) | |
| `created_at`, `created_by` | | `person:<id>` for user, `agent:assistant` for assistant |

- When a past conversation is reopened, figures are **re-fetched** through the API as the current user, so a stale or no-longer-permitted value is never shown from storage. If a figure can no longer be fetched, it shows "No longer available".
- No tool output, prompt text, contact data or raw upload text is stored.

### 2.3 `approvals` (exists after M1; AST-2 adds one kind, no new table)
- Adds `kind = 'assistant_action'`.
- `payload` = `{action_type, params, precondition: {subject_type, subject_id, version}, summary_blocks}`.
- `expires_at` = now + 30 minutes.
- `requested_by = agent:assistant`, `on_behalf_of = person:<user_id>`, `decided_by = person:<user_id>`.
- If the M1 `approvals` shape lacks `expires_at` or `on_behalf_of`, backend adds them in AST-2 PR 12 (a migration).

### 2.4 Help content (no table)
- Help articles are **files in the repo**: `services/api/app/modules/assistant/help/<locale>/<slug>.md`, with front matter `id`, `title`, `screens[]`, `roles[]` (`buyer`/`supplier`), `updated_on`.
- They are loaded at startup into a Postgres `tsvector` in an unlogged cache table `help_index`, rebuilt on every deploy. Its `org_id` is the platform org, so it has `org_id`, `created_at` and `created_by = system:help_loader`.
- Changing an article is a reviewed PR. Hindi articles are a translation of the English ones, reviewed by a fluent human (Q6).

### 2.5 UI registry (AST-2, no table)
`packages/assistant/registry.json` is the single typed list of what the assistant may touch. Frontend owns it; backend reads it to validate model output. It holds:
- `screens`: `{screen_id, route_template, params_schema, roles[]}`;
- `targets`: `{target_id, screen_id, label_en, label_hi}`, which the frontend renders as `data-assist-id`;
- `forms`: `{form_id, screen_id, roles[], fields: {field_id: {type, prefill: allowed|user_verbatim_only|never}}}`;
- `tours`: `{tour_id, steps: [{screen_id, target_id, text_key}]}`, static, with no model involved.

---

## 3. API

**Common rules:**
- Base path `/v1`, customer host.
- The customer auth dependency comes from the login story (a dependency).
- Errors use `{"error": {"code", "message"}}`, as in E0b. Times are ISO-8601 UTC and shown in IST. Money is a string decimal plus `currency`.
- "Owner" below means the user who created the conversation. For anyone else, including an admin of the same org, the endpoint returns **404, not 403**, so conversation ids cannot be enumerated.

| Method and path | Who | Request | Response | Errors |
| --- | --- | --- | --- | --- |
| `POST /assistant/conversations` | any signed-in buyer or supplier member | `{surface, locale, context: {screen_id, params}}` | `{id, locale}` | 422 unknown `screen_id` |
| `GET /assistant/conversations?cursor` | owner | | `{items: [{id, title, last_activity_at}], next_cursor}`, 20 per page | |
| `GET /assistant/conversations/{id}` | owner | | `{id, locale, messages: [{id, role, blocks (figures re-resolved), citations, ui_actions, proposals: [{approval_id, status}]}]}` | 404 |
| `POST /assistant/conversations/{id}/turns` | owner | `{text (1–2000 chars), context: {screen_id, params, form_id?}}` | `{message_id, blocks: [text\|figure\|citation], citations, ui_actions (AST-2), proposals (AST-2): [{approval_id, action_type, summary_blocks, expires_at}], mode: model\|fallback, fallback_articles?}` | 404; 409 `conversation_deleted`; 413 `too_long`; 429 `rate_limited` (default 30 turns per user per hour and 200 per day, Q8); **503 is never returned for a cap or provider failure**: the response is 200 with `mode: fallback` and article matches |
| `DELETE /assistant/conversations/{id}` | owner | | 204. Messages are hard-deleted; the conversation row is kept with `deleted_at` and no title | 404 |
| `POST /assistant/conversations/{id}/ui-events` (AST-2) | owner | `{ui_action_id, outcome: applied\|dismissed\|failed, reason_code?}` | 204 | 404; 422 unknown `ui_action_id` |
| `GET /help/articles?q&locale&screen_id` | any signed-in member | | `{items: [{slug, title, snippet}]}` from full-text search, **0 model calls** | |
| `GET /help/articles/{slug}?locale` | any signed-in member | | `{slug, title, body_md, updated_on}` | 404 |
| `POST /approvals/{id}/approve`, `POST /approvals/{id}/reject` (from M1; AST-2 adds the `assistant_action` executor) | the `on_behalf_of` person only | `{}` | `{status, result_ref}` | 403 not yours; 409 `expired`, `precondition_failed` (the record changed since drafting), `already_decided`; 403 `permission_denied` (role checked again at execution) |

### 3.1 How tools reach data (the isolation mechanism)
- `app/ai/tools/orsyn_api.py` (ai-engineer) holds an `OrsynApiTool` that calls **the same FastAPI app in-process** with `httpx.AsyncClient(transport=ASGITransport(app))`.
- It forwards **the caller's own credential** (session cookie or bearer token) and adds the headers `X-Orsyn-Via: assistant` and `X-Request-Id`.
- **It sends GET only.** Any other method raises before the request is made.
- **Paths come from an allow-list of templates** (§5.3). Arguments are validated: uuids only, enums only. The model never supplies a path or URL.
- **Responses are projected to allow-listed fields** per tool and capped at 4 KB each. Figures keep `{value, currency, source_ref}`.
- **GET handlers must have no side effects.** Read receipts such as "buyer viewed quote" are skipped when `X-Orsyn-Via: assistant` is set. backend adds a test per module (§8).

---

## 4. Events

The append-only `events` table (E0c shape) gets a new `source ∈ {web, pwa, whatsapp, job}`. **Payloads never contain question or answer text, contacts or tool output.**

| Type | Actor | Source | Payload |
| --- | --- | --- | --- |
| `assistant.conversation_started` | person | web/pwa | `{conversation_id, locale, screen_id}` |
| `assistant.turn_answered` | `agent:assistant` | web/pwa | `{conversation_id, message_id, intent, mode, tools: [names], citation_count, figure_count, confidence, model_call_ids, latency_ms}` |
| `assistant.tool_denied` | `agent:assistant` | web/pwa | `{tool, reason: not_allowlisted\|bad_args\|non_get\|api_404\|api_403}` |
| `assistant.output_blocked` | `system:assistant_validator` | web/pwa | `{reason: unreferenced_money\|contact_pattern\|uncited_mandatory\|unknown_citation\|unknown_ui_action\|never_list_action, message_id}` |
| `assistant.fallback_used` | `system:assistant` | web/pwa | `{reason: cap\|provider_unavailable\|validation_failed_twice}` |
| `assistant.ui_action_emitted` (AST-2) | `agent:assistant` | web/pwa | `{ui_action_id, kind, screen_id, form_id?, field_ids?}` (no values) |
| `assistant.ui_action_outcome` (AST-2) | person | web/pwa | `{ui_action_id, outcome, reason_code}` |
| `assistant.action_proposed` (AST-2) | `agent:assistant` | web/pwa | `{approval_id, action_type, subject_ref}` |
| `assistant.action_confirmed` / `.rejected` / `.expired` / `.failed` (AST-2) | person (`system:approvals` for expired) | web/pwa/job | `{approval_id, action_type, result_ref?, error_code?}`. The executed module also writes its own domain event (for example `roadmap.step_started`) with actor = the **person** and `via = assistant` |
| `assistant.conversation_deleted` | person | web/pwa | `{conversation_id, message_count}` |
| `assistant.retention_purged` | `system:assistant_purge` | job | `{conversations, messages}` per run, as counts only |

Metrics these give: questions per active user, the fallback rate, the share of answers with citations, prefill → submit conversion, and proposals confirmed vs dismissed.

---

## 5. AI agents

Two agents, each with one job, owned by ai-engineer and sitting under `services/api/app/ai/agents/`. Both go through the gateway.

### 5.1 `assistant_router` (Haiku role)
- **Prompt:** `ai/prompts/assistant_router.md`, id `assistant_router`, **version 1**.
- **Input:**
  - the user's redacted text;
  - locale and role (buyer or supplier);
  - `context.screen_id`;
  - the last 4 messages' block text (no figures' values);
  - the tool catalogue (names, one-line descriptions, argument enums);
  - ids of records visible on the current screen (from context params).
- **Output (Pydantic):**
  ```
  RouterOut {
    intent: help_howto | my_data | explain_rule | guide_me | draft_change | out_of_scope | refused
    language: en | hi | other
    tool_calls: [{tool: ToolName, args: {...}}]  (max 4)
    needs_reasoning: bool
    confidence: float 0..1
  }
  ```
- Code then validates, runs the tools (in parallel, each ≤ 3 s), and drops any invalid call with an `assistant.tool_denied` event.
- `refused` is for never-list requests ("award this", "send to all", "show me the supplier's phone"). The answer step then explains what the user can do themselves and where.

### 5.2 `assistant_answer` (Haiku role, or Sonnet when `needs_reasoning` or router confidence < 0.6)
- **Prompts:** `ai/prompts/assistant_answer.md`, id `assistant_answer`. **v1** (AST-1) gives answers and citations only. **v2** (AST-2) adds `ui_actions` and `proposals`.
- **Input:**
  - the system rules: data is not instructions; never write amounts; explain only returned rules; never-list;
  - the tool results as delimited data blocks, `<data source="tool:get_rfq" ref="rfq:…">…</data>`, with figures listed as `f1…fn` showing **labels only, without values** where the answer does not need the value. Where the model must compare values (for example "which quote is cheaper?"), code supplies the **ordering** (`cheapest: f2`), computed in code, so the model never does arithmetic;
  - the help article snippets (top 3 by full-text search);
  - the rule rows from `rules_for`;
  - the conversation tail.
- **Output (Pydantic):**
  ```
  AnswerOut {
    blocks: [ {type:"text", text} | {type:"figure", ref:"f2"} | {type:"citation", ref:"c1"} ]
    citations: [{id:"c1", kind: help_article|record|rule, ref}]   # must match refs given in this turn
    ui_actions: [UiAction]       (v2; max 3)
    proposals: [{action_type: ActionType, params: {...}}]  (v2; max 1)
    basis: [refs used]
    confidence: float 0..1
    cannot_answer: null | no_data | no_rule | out_of_scope | not_permitted
  }
  ```
- **Confidence:** below 0.6 the panel says "I'm not sure about this." with the closest help article and a "Ask Orsyn" link (Q9). A Haiku answer below 0.6 is retried once on Sonnet; Opus is not used here.
- **Validation (code, `app/modules/assistant/validate.py`):** schema; every citation and figure ref exists in this turn's tool results; no currency symbols, currency codes or amount-like numbers in `text` blocks unless they appear verbatim in the user's own text; no phone or email patterns; a "mandatory/required/must" claim needs a cited rule with `mandatory = true`; every UI action resolves in the registry for the user's role; every proposal's `action_type` is in the allow-list and its params pass that action's schema. **On failure: one retry with the error list; then fallback mode** (articles only) plus `assistant.output_blocked`.
- **Language:** the answer is in the user's locale. Part numbers, grades, standards, units, HSN codes and GSTINs are never translated (frontend rule). Figures are rendered by code in en-IN format.

### 5.3 Tools (read-only, allow-listed; each one is a GET on an existing endpoint)
| Tool | Calls | Roles | Exists after |
| --- | --- | --- | --- |
| `search_help(q, screen_id?)` | `GET /v1/help/articles` | all | AST-1 |
| `list_my_rfqs(status?)` / `get_rfq(id)` | RFQ module GETs | buyer (own RFQs); supplier (RFQs received) | M1 |
| `list_quotes(rfq_id)` / `get_quote(id)` | quoting GETs (masked by serializer) | buyer; supplier (own quotes) | M1 |
| `get_order(id)` / `list_orders(status?)` | orders GETs | both, own side | M2 |
| `get_roadmap()` / `rules_for(step_id \| hs_prefix, market)` | roadmap and rules GETs | supplier | M1/M4 |
| `get_profile()` | supplier profile GET (own) | supplier | M1 |
| `list_my_pending_approvals()` | approvals GET | both | M1 |

A tool is added to the catalogue only when its endpoint exists and has an isolation test. There are no write tools, no web or URL fetch, and no file-read tool.

### 5.4 Draftable actions (AST-2) and the never-list
**May draft.** Each entry is a typed `ActionType` in `app/modules/assistant/actions.py`, mapped to the existing module service, run as the user, with a precondition version.

| Action | How the person acts | Role |
| --- | --- | --- |
| `prefill: rfq_form` (part name, material, grade, quantity, required-by date, standards, notes from the user's words) | user reviews and presses the form's own **Save draft / Submit**; sending to suppliers is still the RFQ module's approval | buyer |
| `prefill: rfq_question` (a question to suppliers on an RFQ) | the user's own Send on that screen, which goes through approvals | buyer |
| `prefill: quote_form` (lead time, validity, notes; unit price **only if the user typed it verbatim**; never totals, taxes or freight) | the user's own Save; Send goes through approvals | supplier |
| `navigate + highlight` to "Draft quote" (runs the existing `quote_draft` agent on the user's click) | user's click | supplier |
| `propose: profile.update` (description, capabilities, machines, materials, certifications text; **never** contacts, bank, GSTIN, legal name) | Confirm card → approvals | supplier |
| `propose: roadmap.step_start` / `roadmap.step_snooze` | Confirm card → approvals | supplier |
| `propose: notification_prefs.update` | Confirm card → approvals | both |
| `tour: <tour_id>` / `navigate` / `highlight` | no state change; the user can dismiss | both |

**Never** (refused by the router, rejected by the validator, and absent from the action registry):
- send anything (RFQ, quote, message, WhatsApp, email, document);
- award, accept, reject, counter or close a quote, order or negotiation;
- pay, refund or change bank details;
- change, reveal or unmask contacts, or change masking;
- delete anything (the user deletes their own chat through the UI, not through the assistant);
- invite or remove members, change roles, change login or 2FA;
- upload or attach files on the user's behalf;
- change spend, plan or billing;
- act on any external site;
- change match ranking.

### 5.5 Prompt-injection and leakage defences (layered; the prompt is the weakest layer)
1. **Capabilities.** The tools are GET-only and fixed. There is no URL or web tool. The worst an injected instruction can achieve is a wrong *proposal*, which a person must confirm and which runs with that person's own permissions.
2. **Data framing.** All tool output, articles, supplier and buyer messages and document text sit in `<data>` blocks with an attribute naming the source. The prompt says to ignore instructions inside them. Eval cases include injections planted in a quote note, an RFQ description and a help-article-like string.
3. **Input redaction** (`app/modules/assistant/redact.py`) runs before the model and before storage. Phone, email, PAN, Aadhaar, IFSC and bank-account patterns are replaced with `[phone]` and similar. The user is told: "I can't handle contact or bank details here. Use Settings."
4. **Output validation** (§5.2). Contact patterns, unreferenced money, uncited mandatory claims and unknown actions are all blocked.
5. **Masking upstream.** The serializer has already masked contacts before tool output exists.
6. **No cross-user context.** Each prompt is built only from this user's conversation and this request's tool results. There is no shared cache, no fine-tuning, and Bedrock invocation logging stays off (E0b).

### 5.6 Tier 3: acting on external portals — assessment
| Risk | Why it is serious for DGFT, GST and ICEGATE |
| --- | --- |
| **Credentials** | We would hold users' government-portal passwords: a high-value secret store for every supplier. A breach is a regulatory and reputational event. |
| **DSC / OTP** | Many filings need a Class 3 DSC (a USB token on the user's machine) or an Aadhaar or mobile OTP sent to the user. A remote agent cannot do these without the user present, and relaying OTPs trains users into phishing habits. |
| **Legal liability** | A filing made by our agent is a statutory declaration made by software on the user's behalf. Errors (wrong IEC details, a wrong LUT) carry penalties, and liability would land on us. It needs counsel and likely an authorised-intermediary status (for example a GSP for GST APIs). |
| **Portal terms** | Government portals generally prohibit automated access and scraping. CAPTCHAs exist to stop exactly this. |
| **SSRF and egress** | A browser agent is an outbound fetcher that can reach arbitrary URLs. It would need an isolated sandbox with a strict egress allow-list, separate from the VPC. |
| **Prompt injection** | Pages, PDFs and portal messages become instructions to an agent holding live credentials. That is the worst combination. |
| **Reliability** | Portals change layouts, time out and go down for maintenance. Computer-use success rates on multi-step government forms are not near the "zero wrong mandatory steps" bar. |
| **Cost** | Screenshot-driven loops run to dozens of Sonnet or Opus calls per filing, roughly US$0.50–3 each, against free-tier suppliers. |

**Recommended alternative: portal packs (with M4, through the roadmap module):**
- For each external roadmap step (for example IEC on DGFT, LUT on the GST portal, ICEGATE registration, AD code), Help produces a **pack** containing:
  1. a checklist from `packages/rules` (with source and `checked_on`);
  2. the field values the portal will ask for, **copied from the supplier's own verified profile** with a copy button each (no model involved; code maps profile fields to portal fields);
  3. the list of documents needed, linked to what is already uploaded;
  4. a step-by-step walkthrough (help article with screenshots we maintain);
  5. a plain link to the **official domain** (from an allow-list in the rules data).
- The user submits on the portal themselves, then uploads the acknowledgement, and `doc_check` verifies it.
- The cost is about 1 answer call to explain the pack. The pack itself costs 0.

**What would have to be true before we ever build tier 3:**
- an official API or an authorised-intermediary route (GSP/ASP, ICEGATE registered-entity APIs) instead of screen automation;
- a counsel opinion on liability, and user terms that cover it;
- no stored credentials: the user authenticates live (OTP or DSC) in their own session;
- a sandboxed browser with an egress allow-list, recorded sessions and a security review;
- the final Submit still pressed by the user;
- an eval suite on recorded portal flows at 100% on mandatory fields;
- a needs-founder decision with a cost line.

### 5.7 WhatsApp (AST-WA, design direction only)
- The same `assistant_router` and `assistant_answer` agents with `surface = whatsapp`, linked to a user by their verified WhatsApp number (from the WhatsApp onboarding story).
- Answers are plain text, with figures rendered as text plus a short PWA link to the source.
- **No proposals or prefills are confirmed in WhatsApp.** A button reply is weaker authentication and is easy to tap by mistake, so every action becomes a deep link that opens the PWA (login required) on the Confirm card or the prefilled form.
- Voice notes go through Sarvam speech-to-text (`assistant_voice`), with the transcript shown back. Other Indian languages go through Sarvam translation in and out (`assistant_translate`).
- WhatsApp's 24-hour service window applies, and the assistant never initiates messages; outbound templates remain approvals-driven.

---

## 6. Rules

- **Read:** whatever `rules_for` returns. These are layer 1 (every exporter), layer 2 (product code × market) and layer 3 (benefits), as stored in `packages/rules`, each with `source` and `checked_on`.
- **`review_state = awaiting_review` rules** are shown with the plain note "Not yet confirmed by Orsyn", and are never called mandatory.
- Benefit amounts are shown only as figures computed by the benefits module, with a source ref. The model never multiplies a rate.
- No requirement, scheme fact, rate or deadline appears in either prompt. A test greps both prompt files for rule ids, scheme names and percentage patterns.
- Portal packs (§5.6) need rules-curator to add the official portal URL and step list to the relevant rules (a later `rules-change` PR with M4).

---

## 7. Screens

`docs/screens.md` does not exist, so the founders should add these screens (Q10). Frontend builds to `frontend.md`: light theme, the E0 tokens, no sparkles, no "AI-powered" copy, no emoji, no chat bubbles with avatars.

**Name:** "Help" in the side panel and top bar, "मदद" in Hindi. Copy is plain: "Ask a question", "Show me", "Fill this in for me". Assistant messages carry no label like "AI"; they sit under the heading "Help".

**Font:** add **Noto Sans Devanagari** through `next/font` for Hindi. Public Sans has no Devanagari.

| Screen / element | Holds | Empty | Loading | Error |
| --- | --- | --- | --- | --- |
| **Help panel** (in `AppShell`; a right-side panel at 1440px, a full-screen sheet at 390px; opened from a "Help" item in the top bar and with `?`) | Question box (2000-character limit shown), answer blocks: text, **figures in IBM Plex Mono as links to their source**, citations as numbered links ("Help: Sending an RFQ", "RFQ R-1042", "Rule: IEC required, checked 01 Oct 2026"). Suggested questions for the current `screen_id` come from the registry, not a model. Language switch EN / हिं | "Ask how to do something, or about your RFQs, quotes and orders." plus 3 screen-specific suggestions | "Looking…" with the question box disabled; after 10 s, "Still looking…" | Fallback mode: "Help can't answer right now. These articles may help:" plus a list; rate limited: "You've asked a lot this hour. Try again at 15:40 IST."; network error: "Couldn't send. Retry" |
| **History** (inside the panel) | Own past conversations: title and time in IST; Delete with a confirm ("Delete this conversation? This can't be undone.") | "No past questions." | skeleton rows | error plus Retry |
| **Help article view** (inside the panel, and `/help/[slug]`) | Title, body, updated date | n/a | skeleton | "Couldn't load this article." |
| **Highlight** (AST-2) | Outline around the `data-assist-id` element, a short label from the registry, focus moved to it, Esc or "Done" to clear. Nothing on the page is dimmed | n/a | n/a | target missing: "That button isn't on this screen." plus an outcome event `failed` |
| **Tour** (AST-2) | Step x of n, Next / Back / End, navigates between registered routes | n/a | n/a | same as highlight |
| **Prefilled form** (AST-2, on the RFQ, RFQ-question and quote forms) | Filled fields carry a plain marker "Filled by Help — check" until edited. A summary line above the form reads "Help filled 5 fields. Check them, then save." The form's own buttons are unchanged and **nothing auto-submits**. An Undo restores the previous values | n/a | n/a | invalid prefill values are dropped and listed: "Couldn't fill: quantity" |
| **Confirm card** (AST-2, in the panel) | "Help wants to: start the roadmap step 'Get IEC'." shown as a before → after table for profile changes, with **Confirm** and **Dismiss** and an expiry in IST | n/a | "Confirming…" | 409 expired: "This expired. Ask again."; 409 precondition: "This changed since Help drafted it. Ask again."; 403: "You don't have permission to do this." |

- **Accessibility:** the panel is a labelled `complementary` region. Answers are announced via `aria-live="polite"`. Every target is 44 px, and everything is keyboard reachable.
- **Supplier PWA at 390px:** the panel is a full-screen sheet and the highlight scrolls its target into view.
- **The frontend executor** (`apps/web/lib/assistant/execute.ts`) validates every UI action against `registry.json` with Zod and **ignores unknown ones** (sending an `outcome: failed` event). It navigates only via `router.push` to registry routes and never to an external URL or arbitrary path.

---

## 8. Tests and evals (qa-evals; api tests in `services/api/tests/`, web tests in `apps/web/tests/`, per E0 §1.3)

### 8.1 One test per proposed "Done when" clause
| Clause | Test |
| --- | --- |
| AST-1 (a) answers cite help, own records or rules, in EN and HI | `test_turn_answer_has_valid_citations` (stub gateway returns AnswerOut; every citation resolves to this turn's tool results; an unknown ref → retry → fallback). `test_hindi_locale_roundtrip`. Web: citations render as links. Eval suite §8.3 |
| AST-1 (b) figures from the server with a source; the model writes no money | `test_figure_rendered_from_api_value_with_source_ref`. `test_validator_blocks_unreferenced_amounts` (parametrised: "₹4,500", "INR 4500", "4.5 lakh", "$12", "Rs."). `test_comparison_order_computed_in_code`. Web: the figure is an anchor to the source and the browser does no arithmetic |
| AST-1 (c) data only through the API as the user; no other org or masked contact | `test_tool_client_forwards_user_credential_and_get_only`. `test_tool_client_rejects_non_allowlisted_path_and_bad_ids`. Isolation and masking negatives in §8.2 |
| AST-1 (d) cost logged; cap or provider fallback with 0 calls | `test_each_turn_writes_model_calls_with_org_and_feature`. `test_cap_blocked_returns_fallback_without_provider_call`. `test_provider_unavailable_returns_fallback` |
| AST-1 (e) owner-only, deletable, purged | `test_other_user_same_org_gets_404`. `test_delete_hard_deletes_messages`. `test_purge_job_deletes_after_purge_after` (frozen time) |
| AST-2 (a) registry-only UI actions | `test_validator_rejects_unknown_screen_target_form_field`. Web: `execute.test.ts` ignores unknown actions and an external `href` |
| AST-2 (b) no auto-submit | Web: `prefill.test.tsx` checks that no submit or network mutation fires after prefill, that markers show and that Undo restores. `test_prefill_never_fields_rejected` (contacts, totals, tax) and `test_price_prefill_requires_user_verbatim` |
| AST-2 (c) Confirm card → approvals → runs as the user | `test_proposal_creates_pending_approval_and_no_state_change`. `test_confirm_executes_with_current_permissions` (downgrade the role between propose and confirm → 403). `test_precondition_changed_returns_409`. `test_expired_returns_409` |
| AST-2 (d) never-list refused; zero unapproved actions | `test_never_list_actions_absent_from_registry` (a static check of `actions.py` against the never-list). `test_router_refusal_paths`. Eval metric "unapproved actions = 0" |

### 8.2 Negative tests (always)
- **Org isolation:**
  - Two orgs, each with RFQs and quotes. Org B's ids in the user text, the context params and planted in router output → the API returns 404 → the tool is denied and nothing about B appears in the prompt (captured from the stub gateway), the stored messages or the logs.
  - Conversations of org A user 1 are invisible to org A user 2 and to org B (404).
  - Approval confirm by a non-`on_behalf_of` user → 403.
- **Masking before award:**
  - A buyer asks for a supplier's phone, email or website before award → the prompt (captured), answer, stored message and logs contain no contact. The router intent is `refused`.
  - After award, the answer may link to the order screen where contacts show, but contacts still never pass through the model (Q11).
  - A supplier asking about their own customers sees what the API shows them (unmasked by rule).
  - A planted contact in a supplier's quote note ("call me on 98…") is blocked by the output filter.
- **Approval required:**
  - No route in `app/modules/assistant/` imports a sender (WhatsApp, email, RFQ send, quote send).
  - The tool client cannot issue POST, PUT, PATCH or DELETE.
  - Every `assistant_action` executor checks `approvals.status = approved` and `decided_by = on_behalf_of`.
- **Side-effect-free GETs:** each tool's endpoint called with `X-Orsyn-Via: assistant` writes no event and no read receipt.
- **Prompt-file hygiene:** no rule text, scheme names, rates or customer data in the prompt files.
- **PII:** the redactor is tested on phone (+91 and 10-digit), email, PAN, Aadhaar, IFSC and account patterns in EN and HI text. `model_calls` and events have no free-text columns.

### 8.3 Evals: `evals/assistant/` (ai-engineer builds them, qa-evals runs them)
- **Cases:** at least 120 at AST-1 and at least 60 more at AST-2. Each has: role, locale, screen, fixture org data (consented, anonymised), question, expected intent, expected tool calls, expected citations, expected figures (refs), forbidden content, and expected UI actions or proposals.
- **Mix:** 30% how-to, 30% my-data status, 15% rule explanations, 10% Hindi across categories, and 15% adversarial (cross-org ids, contact requests, injections in quote notes, RFQ text and documents, "award it for me", "what's the total with GST?" when no computed total exists).
- **Every real case Nithish brings becomes a permanent eval case.**

| Metric | Pass mark (blocks PR) |
| --- | --- |
| Cross-org leaks (any other-org id, name or value in prompt or answer) | **0** |
| Masked contact leaks before award | **0** |
| Unapproved actions (any state change without an approved record; any never-list action emitted past the validator) | **0** |
| Money written by the model (amounts not via figure ref) reaching the user | **0** |
| Invented requirements (a mandatory claim without a cited `mandatory` rule) | **0** |
| Citation accuracy (every citation exists and supports the sentence; graded by a rubric with a Sonnet grader plus 10% human spot-check) | **≥ 95%** |
| Answer grounding (answer correct and supported by cited sources) | **≥ 90%** EN, **≥ 85%** HI |
| Router tool-call correctness (right tool and args) | **≥ 90%** |
| UI action correctness (right screen, target or form; AST-2) | **≥ 90%** |
| Prefill field accuracy (AST-2; fields match the user's words, none invented) | **≥ 90%**, with 0 invented price values |
| Cost | reported per case; mean ≤ US$0.02 per turn |

Evals use recorded fixtures with the gateway stubbed for CI determinism. A separate `--live` run (manual, dev) measures real model quality before each prompt version bump.

---

## 9. Cost

Prices come from `app/ai/prices.py` (E0b). Planning assumptions, to be confirmed: Haiku role about US$1 / 5 per 1M input/output tokens, Sonnet about US$3 / 15.

| User action | Model calls | Estimate |
| --- | --- | --- |
| Open Help, read an article, search articles, tour, highlight, history | **0** | US$0 |
| Simple turn (how-to, status) | 2 Haiku: `assistant_route` (~2.5k in / 150 out) plus `assistant_answer` (~4k in / 300 out) | **≈ US$0.009** |
| Reasoning turn (explain a rule, compare quotes, draft a prefill) | 1 Haiku route plus 1 Sonnet answer (~6k in / 500 out) | **≈ US$0.029** |
| Validation retry (rare) | +1 answer call | +US$0.006–0.025 |
| Confirm or Dismiss a proposal | 0 | US$0 |
| **Average turn** (70% simple, 30% reasoning, 5% retries) | about 2.1 calls | **≈ US$0.015 (≈ ₹1.3)** |
| **Average conversation** (about 5 turns) | about 10 calls | **≈ US$0.07 (≈ ₹6)** |
| WhatsApp voice (AST-WA) | + Sarvam speech-to-text per voice note | Sarvam price TBD in `prices.py` |

- **Feature names for cost logging:** `assistant_route`, `assistant_answer`, later `assistant_translate` and `assistant_voice`. Eval runs log `eval_assistant`.
- **Volume example:** 200 active users × 10 conversations a month ≈ **US$140 a month**. Bedrock prompt caching of the static system prompt and tool catalogue could cut input cost substantially; ai-engineer measures it, and it is not assumed above.
- **Caps:** the suggested default per-org cap for the assistant features is **US$5 a month** (about 70 conversations), plus a feature cap on `assistant_*` under the global fuse (Q8). Above the cap, Help keeps working in fallback mode at US$0.
- **Infrastructure:** nothing new. There are two Postgres tables, an unlogged index table and one EventBridge Scheduler rule plus a consumer on the existing SQS pattern for the daily purge. The cost is about **US$0 (₹0)**: the scheduler and SQS sit inside the free tier at this volume, and storage is small (about 2 KB per message). Expected monthly AWS change ≈ **₹0 / US$0**, plus the model spend above.

---

## 10. PR split

**Prerequisites:** E0, E0b (gateway with caps and `model_calls`), E0c (`orgs`, `events`), customer login and org membership, the M1 `approvals` table and masking serializers, and the M1 RFQ and quote GET endpoints. AST-2 also needs the M2 orders module and the roadmap module.

### AST-1: help and answers (labels M2 or as decided, Q2)
| # | PR | Builder(s) | ~Lines | Labels |
| --- | --- | --- | --- | --- |
| 1 | Migration (reversible) `assistant_conversations`, `assistant_messages` (composite FK on `org_id`); models; repository that requires `(org_id, user_id)`; tests | backend, qa-evals | ~300 | needs-founder, security-review |
| 2 | Help module: article loader (front matter, EN and HI), `help_index` full-text search, `GET /help/articles*`, 10 seed articles in EN with HI versions (content from Q6); tests | backend, qa-evals | ~380 | |
| 3 | `OrsynApiTool` (in-process ASGI, forwarded credential, GET-only, path allow-list, projection, 4 KB cap), the tool catalogue for the M1 endpoints, `X-Orsyn-Via` handling; isolation tests | ai-engineer, qa-evals | ~380 | security-review |
| 4 | `redact.py` and `validate.py` (citations, figure refs, money patterns, contact patterns, uncited mandatory claims); tests | ai-engineer, qa-evals | ~350 | security-review |
| 5 | Agents `assistant_router` and `assistant_answer` (Pydantic schemas), prompts `assistant_router.md` v1 and `assistant_answer.md` v1, rows in `routing.py`, the Haiku→Sonnet rule, prices; stub-gateway tests | ai-engineer, qa-evals | ~380 | security-review |
| 6 | `evals/assistant/` with the first 120 cases, the scorers (leaks, money, citations, grounding, tool calls) and a report with cost per case | ai-engineer, qa-evals | ~400 (cases JSONL excluded) | |
| 7 | Assistant API: conversations, turns (orchestration, rate limit, fallback), delete, events, figure re-resolution; tests per §8.1 | backend, qa-evals | ~390 | needs-founder (deletion), security-review |
| 8 | Purge job (EventBridge Scheduler → SQS consumer → hard delete after `purge_after`), plus the infra rule | backend, infra, qa-evals | ~200 | needs-founder (data deletion), security-review |
| 9 | Web: the Help panel in `AppShell` (question box, block renderer with figure and citation links, fallback, rate-limit and error states, `aria-live`) | frontend, qa-evals | ~390 | |
| 10 | Web: history, delete, article view, Hindi strings and Noto Sans Devanagari, suggested questions by screen | frontend, qa-evals | ~320 | |

### AST-2: guidance and drafts (label M3)
| # | PR | Builder(s) | ~Lines | Labels |
| --- | --- | --- | --- | --- |
| 11 | `packages/assistant/registry.json` plus its JSON schema; `data-assist-id` on registered targets; the executor for `navigate`, `highlight` and `tour` (Zod-validated, ignores unknown actions); the `ui-events` call; tests | frontend, qa-evals | ~390 | |
| 12 | `approvals` kind `assistant_action`: `actions.py` registry (allow-list), executors run as the user with role re-check and precondition, `expires_at` / `on_behalf_of` (migration if missing), expiry job, `ui-events` endpoint, events; tests | backend, qa-evals | ~390 | needs-founder (approval path, migration), security-review |
| 13 | `assistant_answer` v2 (UI actions and proposals), validator registry checks, router `draft_change` / `refused` cases, 60 more eval cases including never-list and injection cases | ai-engineer, qa-evals | ~380 | security-review |
| 14 | Web: the prefill executor on the RFQ, RFQ-question and quote forms (markers, Undo, never-fields, verbatim price check from the server's flag) | frontend, qa-evals | ~350 | security-review |
| 15 | Web: the Confirm card (before → after, Confirm and Dismiss, expiry and error states) | frontend, qa-evals | ~250 | |

**Order and parallelism:**
- AST-1: 1 → 7 → 8. 2, 3 and 4 run in parallel after 1. 5 needs 3 and 4. 6 needs 5. 7 needs 2 and 5. 9 needs 7. 10 needs 9.
- AST-2: 11 and 12 run in parallel. 13 needs 12. 14 needs 11 and 13. 15 needs 12 and 11.
- **security-reviewer** is required on PRs 1, 3, 4, 5, 7, 8, 12, 13 and 14. **product-reviewer** checks each story at the end.

**Later stories:**
- **AST-WA:** WhatsApp surface plus Sarvam voice and translation, about 4 PRs. Needs the WhatsApp webhook story.
- **PACK (with M4):** portal packs, as roadmap-module work plus a rules-curator `rules-change`.

**File ownership** (no overlap):

| Owner | Files |
| --- | --- |
| backend | `app/modules/assistant/{api,repo,orchestrate,actions}.py`, `app/modules/help/**`, migrations, `jobs/assistant_purge.py` |
| ai-engineer | `app/ai/agents/assistant_*`, `app/ai/prompts/assistant_*.md`, `app/ai/tools/orsyn_api.py`, `app/modules/assistant/{redact,validate}.py` (validation is agent-safety code, Q12), `evals/assistant/` |
| frontend | `apps/web/**/assistant/**`, `packages/assistant/registry.json` |
| infra | the scheduler rule |
| qa-evals | tests |

---

## 11. Flags

- **needs-founder: yes.**
  - **Migrations:** two new tables, plus possibly columns on `approvals`.
  - **Approval path:** a new `approvals` kind whose executors change state on confirm.
  - **Data deletion:** user delete and the retention purge job.
  - **Spend:** a new per-turn model spend, the per-org assistant cap and the rate limits.
  - **Data residency:** the answer model (Sonnet) runs through the Global profile with user data in prompts (E0b Q3).
- **security-review: yes.**
  - **Isolation:** the tool client forwards the user credential; the conversation scoping.
  - **Masking:** prompts, outputs and stored messages.
  - **Approvals:** the executors, the re-check of permissions and the never-list.
  - **AI:** prompt injection through supplier and buyer content, and the guarantee of no fetch tool (SSRF).
  - **Auth:** credential forwarding inside the process, the `X-Orsyn-Via` header and the GET side-effect rule.
  - Tier 3, if ever proposed, adds secrets, IAM and egress.
- **rules-change:** no for AST-1 and AST-2. Yes later for portal-pack URLs and steps (M4).

---

## 12. Open questions

1. **Key, milestone and "Done when".** Confirm the keys `AST-1` / `AST-2` / `AST-WA`, the proposed "Done when" in §1.2, and the placement: AST-1 after M1 (built alongside M2), AST-2 after M2 (alongside M3). Or should Help wait until after M5 so it doesn't slow Phase 1?
2. **Phase 1 priority.** Should AST-1 delay any M2 story? The recommendation is no: build it only once M2's critical path is staffed.
3. **Name.** Is "Help" / "मदद" right?
4. **Retention.** Keep conversations for 90 days after last activity, then hard-delete? Is that consistent with the privacy terms and the DPDP Act? Counsel should confirm.
5. **Admin visibility.** Confirm that org admins **cannot** read members' conversations (recommended). Can Orsyn staff read them for support? The recommendation is no in Phase 1; events and costs only.
6. **Help content.** Who writes the first 10 articles and their Hindi versions, and who reviews the Hindi for fluency? Articles are needed before PR 2 merges.
7. **Hindi model quality.** Is Claude's Hindi acceptable for answers (eval ≥ 85%), or should all Hindi go through Sarvam translation from AST-1? Decide after the first live eval run.
8. **Caps and rate limits.** Confirm the default per-org assistant cap of US$5 a month, the feature fuse value, and the user limits of 30 turns an hour and 200 a day. Do free suppliers get the same cap as buyers?
9. **"Ask Orsyn" escalation.** When Help is unsure, where does the user go: a support email, a WhatsApp number or a ticket? There is no support module today.
10. **`docs/screens.md`.** Who adds the Help panel, Confirm card and prefill markers to it? Do the founders want to see a sketch before PR 9?
11. **After award.** May the assistant *mention* an awarded supplier's contact in an answer, or only link to the order screen? The recommendation is link only: contacts never go through the model.
12. **Validator ownership.** Should `redact.py` and `validate.py` sit with ai-engineer (proposed) or backend? They gate what the model can do, so they need one clear owner.
13. **Tier 3 appetite.** Confirm that browser automation on DGFT, GST and ICEGATE stays out of Phase 1, and that portal packs with M4 are the plan. Are any GSP/ASP partnerships already under discussion?
14. **Haiku role model.** The assistant depends on the Haiku-role replacement (E0b Q6). Its router eval must pass on the chosen model.
