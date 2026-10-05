# KYC — Supplier and buyer verification (KYB/KYC), badges, consent and staff review

Status: draft, waiting for founder OK. Author: architect. Date: 2026-10-05. Story key **KYC is provisional** (Q1).

Inputs read: `CLAUDE.md`, `.claude/agents/*`, `docs/build-plan.md` (stub: only E0), `docs/screens.md` (stub), `docs/architecture.md` (stub), `packages/rules/{README.md,schema.json}`, `docs/plans/{E0-repo-ci,E0b-admin-provider-keys,E0d-ops-console-analytics,AST-assistant}.md`. There is no application code yet. This plan builds on:
- **E0b**: admin host and staff auth, `provider_credentials`, `SecretStore`, `PlatformScope`, audit helper;
- **E0c**: Alembic, `orgs` with a platform org, the append-only `events` table;
- **E0d**: the ops console shell, the staff "reveal with reason" pattern, `orgs.status`, `failed_jobs`, alerts.

It changes nothing in those plans. Where it needs more from them, it says so as an additive migration.

Vendor facts checked on 2026-10-05:
- **Cashfree Secure ID** documentation index, read directly. It lists GSTIN verify, PAN, bank account verification, reverse penny drop, IFSC, name match, DigiLocker and Aadhaar masking. The GSTIN response has legal name, trade name, status, address, registration date, taxpayer type and constitution. **That page shows no return filing status and no CIN, Udyam or IEC endpoints.**
- **Razorpay Route** "create linked account" required fields (Appendix C), read directly.
- **Surepass, Signzy, IDfy and Perfios**: home pages only, which list KYB, bank, DigiLocker and AML capabilities in general terms.

**No provider prices are public on the pages read. Every price in this plan is "to quote".** Statements about Aadhaar, DPDP and sanctions law are design inputs for counsel to confirm, not legal advice.

Founder's ask, verbatim: "What about KYC".

---

## 1. Goal

Make "verified Indian suppliers" literally true. Every supplier and buyer badge comes from a dated check record against a government-backed source, a supplier proves its business in about two minutes on a phone by entering a GSTIN, and KYC data stays private, consented, masked and deletable.

### 1.1 Proposed "Done when" (`docs/build-plan.md` has no KYC story; the founder confirms the text, Q1)

> (a) a supplier can start verification on the PWA or WhatsApp by entering only a GSTIN (typed, or read from a photo of the GST certificate); legal name, trade name, constitution, state and principal address are filled from the GST check and the supplier only confirms;
> (b) no check runs before the person's consent for that purpose is recorded with the notice version, time and channel; after consent is withdrawn, no new checks or re-checks run;
> (c) each GSTIN, PAN, Udyam, IEC, CIN/LLPIN, bank account (penny drop with name match), authorised signatory and sanctions check writes a check record with source, checked on, provider reference and re-check date; a full Aadhaar number is never collected, stored, logged or sent to a model;
> (d) buyers see badges only; each badge links to the check records behind it and disappears when a check fails, expires or is withdrawn; KYC documents, PAN, bank details and (before award) GSTIN, legal name and street address never appear in buyer-facing API responses, logs, exports or prompts;
> (e) a name mismatch, potential sanctions hit, unconfirmed signatory, duplicate identifier or provider failure opens a staff review case; only an Orsyn admin owner resolves it, with a reason, and the decision is in the event log;
> (f) buyers are screened against the UN, OFAC, EU and India lists at signup, again whenever a list changes, and in a weekly full re-screen; a potential hit on a buyer holds their RFQs until staff resolve it;
> (g) uploaded KYC documents are checked for type and size, stored only in the private KYC bucket, and opened only through URLs valid for 60 seconds; a `doc_check` extraction is used only after the supplier or staff confirms it;
> (h) re-checks run on schedule, and the supplier sees what is due and when;
> (i) dev and CI run on the fake provider; provider keys live only in Secrets Manager; every provider call and model call has its cost logged;
> (j) the payload Razorpay Route needs for a linked account can be built from stored, verified records without asking the supplier again (a mapping test, with no Razorpay call in this story).

### 1.2 What "verified" means (proposed policy, founder confirms in Q2)

| Level / badge (buyer-facing label) | Requires (all checks `pass`, not expired) | Who sees it | Milestone |
| --- | --- | --- | --- |
| **Verified supplier**, the composite the matcher uses | GST verified + PAN verified + Signatory confirmed + Screening clear | buyers, the supplier | **M1** |
| **GST verified** | GSTIN check: status `Active`, PAN segment matches the PAN check, org legal name confirmed by the supplier | buyers | M1 |
| **PAN verified** | business PAN valid, name on PAN matches the GST legal name (normalised) | buyers | M1 |
| **MSME (Udyam) registered** | Udyam check active; category (micro / small / medium) is shown as returned, not computed | buyers | M1 (optional for the supplier) |
| **Company registered (MCA)** | CIN or LLPIN active, for companies and LLPs only | buyers | M1 (where applicable) |
| **Export-ready: IEC verified** | IEC check active, plus IEC's PAN equals the business PAN | buyers | M1 (exporters) |
| **Bank verified** | penny drop success + name match `high`, **or** staff-approved mismatch | buyers (label only) | M1 build, **required before the first payout (M2)** |
| Buyer: **GST verified** (Indian) / **Business verified** (foreign: registry evidence + domain check + screening clear) | as stated | suppliers | M1 |
| Internal only: **Signatory confirmed**, **Screening clear** | §2.3 | staff, and the org's own users | M1 |

The badge logic lives **in code** (`app/modules/verification/policy.py`) as a typed table: badge → required check types → re-check interval. It is product policy, not an export rule. The founder approves it in this plan, and later changes go through a PR. A badge is **computed on read** from the latest passing, unexpired checks, so it can never be out of step with its checks. No badge table is stored.

### 1.3 Design choices (simplest that meets "Done when")

- **API checks first; documents are a fallback.** A deterministic API check confirms a fact; a document is evidence, or a way to save typing. Most suppliers upload nothing.
- **One `verification` tool interface** (`app/ai/tools/verification/`) with per-check-type routing to a provider. It works like model routing, but it is plain HTTP: no model is involved. There is a `FakeVerificationProvider` for dev and CI. Keys come from E0b `SecretStore` slots.
- **The primary provider is a recommendation only (Appendix B).** **Cashfree Secure ID** is recommended for GSTIN, PAN, bank (penny drop and reverse penny drop), name match and DigiLocker, subject to quotes. Udyam, IEC, CIN/LLPIN and GST filing status go to whichever shortlisted provider offers them in its quote, and may be the same one (Q3). There is one interface and two adapters at most.
- **Sanctions screening is done in-house on list data, not by a model.** A nightly job loads the official lists, or a licensed aggregate (Q5), into Postgres. Matching runs in SQL with `pg_trgm` plus normalisation in code. Potential hits go to staff. There is no auto-clear, and no auto-block beyond the hold in (f).
- **Name matching is code, not a model.** The normaliser strips `M/s`, `Pvt Ltd`/`Private Limited`/`P. Ltd`, `LLP`, `&`/`and`, punctuation and honorifics, then compares tokens. The provider's name-match score is a second input. Thresholds are constants: `high` → pass, `medium` or `low` → staff review.
- **Format validators in code run before any paid call:**
  - the GSTIN check digit (the GSTN mod-36 algorithm);
  - PAN `^[A-Z]{5}[0-9]{4}[A-Z]$` and its 4th character (entity type);
  - IFSC `^[A-Z]{4}0[A-Z0-9]{6}$`;
  - Udyam `UDYAM-XX-00-0000000`;
  - CIN and LLPIN shapes;
  - IEC (10 characters).

  This blocks cost from typos.
- **PAN, IEC and Udyam are derived wherever possible.** The GSTIN's characters 3–12 are the PAN, so the supplier never types PAN separately. IEC is now usually the PAN, so the check is attempted with the PAN first. Udyam is asked for only if the supplier says they have it, or if the provider offers PAN → Udyam.
- **Sensitive values are encrypted at field level with one KMS key.** PAN and bank account numbers use KMS `Encrypt`/`Decrypt` directly; they are under 4 KB, so there is no envelope library. The encryption context is `{org_id, table, column}`, which binds each ciphertext to its org. The DB holds the masked form and an HMAC for duplicate detection. GSTIN, Udyam, IEC and CIN are public-register identifiers and are stored in plaintext.
- **No raw provider response is persisted or logged.** Only allow-listed, normalised fields are stored, together with `provider_ref` (the vendor's request or reference id) and `response_sha256`. Contact fields that some GST APIs return, such as taxpayer email or mobile, are **dropped in the adapter**, never stored. This meets rule 3 (traceability), rule 5 (contacts) and DPDP data minimisation.
- **Sensitive inputs are collected in the PWA, not in WhatsApp chat.** WhatsApp collects the GSTIN (public) and the confirmation, then sends a signed deep link to the PWA for bank details, uploads and consent text. Bank numbers and documents in chat would sit in Meta's systems and in our webhook logs.

### 1.4 Deliberately not building

- **Any Aadhaar-number flow.** Aadhaar is not needed for B2B verification: GST + PAN + signatory cover it. Orsyn will not be an AUA/KUA and will not do Aadhaar authentication, offline XML or QR verification. If a signatory's identity must be confirmed beyond a PAN match, it is done through **DigiLocker consent pulling the PAN document**, not Aadhaar. If a future flow needs DigiLocker Aadhaar, only the masked document (last 4 digits) would be shown, and nothing would be stored beyond `name`, `last4` and the DigiLocker reference (Q7).
- **Scraping government portals** (GST public search, MCA, DGFT, Udyam). They use captchas, scraping breaks their terms, and it is fragile. Direct government APIs (GSP access, Protean PAN for entities) need registrations Orsyn does not have (Appendix B).
- Video KYC, liveness, face match and OCR of identity cards.
- Automated foreign company-registry APIs (Companies House, OpenCorporates). Foreign registry evidence is an uploaded document plus staff confirmation. Automation is a follow-up once foreign buyer volume justifies it.
- Credit scoring, financials, GST return analytics and litigation checks.
- Creating Razorpay linked accounts. That is M2; this story only proves the mapping (Appendix C).
- Malware scanning of uploads (Q9). Uploads are mitigated by type sniffing, size limits and `Content-Disposition: attachment`.
- Orsyn's own business KYC. That is a founder checklist (Appendix A), not code.

---

## 2. Ontology impact

Every new table has `id` (uuid), `org_id`, `created_at` (timestamptz UTC) and `created_by` (`person:<uuid>`, `agent:<name>` or `system:<component>`), following the E0b convention. KYC creates no commercial documents or PO lines, so the document-line → PO-line link does not apply. When an invoice or PO (M2) prints a supplier's GSTIN, it references `org_registrations.id`, so the printed value traces to its check.

### 2.1 `consents` (append-only)
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | the org the person acts for |
| `person_id` | uuid FK persons | the data principal giving consent |
| `purpose` | text check in (`kyc_business_verification`, `kyc_bank_verification`, `kyc_signatory_verification`, `sanctions_screening`, `badge_display`, `payouts_share_with_razorpay`) | `payouts_share_with_razorpay` is captured in M2 |
| `action` | text check in (`granted`, `withdrawn`) | withdrawal is a new row; rows are never updated |
| `notice_id`, `notice_version`, `notice_sha256` | text, int, char(64) | the exact notice text shown (repo file, §2.9) |
| `locale` | text | `en`, `hi` |
| `channel` | text check in (`pwa`, `web`, `whatsapp`) | |
| `evidence` | jsonb | `{ip_hash, user_agent_family}` for web; `{wa_message_id}` for WhatsApp. No phone numbers |
| `created_at`, `created_by` | | `person:<id>` |

- A view `current_consents` gives the latest action per (`person_id`, `purpose`).
- A trigger raises an error on UPDATE or DELETE. The only exception is the DPDP erasure job, which may null `evidence` (§2.10).

### 2.2 `kyc_checks` (append-only; one row per provider call or in-house check)
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | the org being verified |
| `subject_type` | text check in (`org`, `person`, `bank_account`, `registration`) | |
| `subject_id` | uuid | |
| `check_type` | text check in (`gstin`, `gst_filing`, `pan`, `udyam`, `iec`, `cin`, `llpin`, `bank_penny_drop`, `bank_reverse_penny_drop`, `name_match`, `signatory`, `sanctions`, `domain`, `registry_doc`, `duplicate`) | |
| `input_masked` | text | e.g. `27AAAAA****1Z5`, `XXXXXX1234 / HDFC0001234`. Never the full PAN or account number |
| `input_hmac` | char(64) | HMAC-SHA256 with a key held in Secrets Manager (`orsyn/<env>/kyc/hmac`); used for duplicate detection |
| `provider` | text | `cashfree`, `<secondary>`, `fake`, `inhouse` |
| `upstream_source` | text | `GSTN`, `ITD (PAN)`, `Udyam (MSME)`, `DGFT`, `MCA`, `NPCI/IMPS bank`, `UN/OFAC/EU/IN lists v<id>`, `DNS/RDAP`, `staff` |
| `provider_ref` | text null | the vendor's reference or request id: the "provider response reference" for rule 3 |
| `response_sha256` | char(64) null | hash of the raw response bytes, which are not stored |
| `result` | jsonb | **allow-listed normalised fields** per check type (§2.2.1) |
| `outcome` | text check in (`pass`, `fail`, `mismatch`, `potential_hit`, `not_found`, `error`, `pending`) | |
| `error_code` | text null | enum (`timeout`, `provider_down`, `invalid_input`, `rate_limited`, `auth_failed`); no raw vendor text |
| `checked_at` | timestamptz | UTC; shown in IST |
| `recheck_due_at` | timestamptz null | from `policy.py` |
| `expires_at` | timestamptz null | badge validity end; after this the badge drops even if no re-check ran |
| `supersedes_id` | uuid FK kyc_checks null | the earlier check of the same subject and type |
| `cost_amount`, `currency` | numeric(12,4), char(3) | `Decimal`, computed in code from `verification/prices.py` (rows: provider, check type, unit price, currency, `source` = contract or quote reference, `checked_on`); `INR` expected |
| `feature` | text | cost-logging feature name `kyc_<check_type>` |
| `request_id` | text | |
| `created_at`, `created_by` | | `person:<id>` when user-initiated; `system:kyc_recheck` or `system:sanctions_screen` otherwise |

Indexes: (`org_id`, `check_type`, `checked_at desc`), (`input_hmac`), (`recheck_due_at`) where `outcome = 'pass'`.

#### 2.2.1 Allow-listed `result` fields
| Check | Stored | Dropped in the adapter, never stored |
| --- | --- | --- |
| gstin | `gstin_status`, `legal_name`, `trade_name`, `constitution`, `taxpayer_type`, `registration_date`, `cancellation_date`, `state_code`, `principal_address` (structured), `nature_of_business[]`, `pan_segment_matches` (bool) | taxpayer email and mobile, any person's contact details |
| gst_filing | `periods[]: {return_type, period, filed_on, status}`, last 12 only | |
| pan | `pan_status`, `name_on_pan_normalised`, `entity_type`, `name_match: high\|medium\|low` | Aadhaar seeding details beyond `aadhaar_linked: bool` (if returned), date of birth |
| udyam | `udyam_status`, `enterprise_name`, `category`, `category_year`, `major_activity`, `nic_codes[]` | owner's name, mobile and email |
| iec | `iec_status`, `firm_name`, `pan_matches` (bool), `last_updated_on` | contact details |
| cin / llpin | `company_status`, `name`, `incorporation_date`, `class`, `directors_or_partners[]: {name_normalised, din_masked}` | director addresses and contacts |
| bank_* | `account_exists`, `name_at_bank_normalised`, `ifsc`, `bank_name`, `name_match: high\|medium\|low`, `name_match_score` | full account number (it lives encrypted in `bank_accounts` only) |
| sanctions | `list_version_ids[]`, `candidates[]: {entry_id, list, score, matched_on}` | |
| domain | `domain`, `resolves`, `has_mx`, `https_ok`, `registered_on` (RDAP), `email_domain_matches` | WHOIS registrant contact |

### 2.3 `org_registrations` (the current verified identifiers of an org)
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | |
| `kind` | text check in (`gstin`, `pan`, `udyam`, `iec`, `cin`, `llpin`, `foreign_registry`) | |
| `value` | text null | plaintext for public-register ids (`gstin`, `udyam`, `iec`, `cin`, `llpin`, `foreign_registry`) |
| `value_ciphertext` | bytea null | for `pan` only (KMS, with the encryption context) |
| `value_masked` | text | always set |
| `value_hmac` | char(64) | duplicate detection across orgs |
| `country` | char(2) | `IN`, or the registry country |
| `is_primary` | bool | one primary GSTIN per org (multi-state suppliers have several) |
| `state` | text check in (`pending`, `verified`, `failed`, `withdrawn`, `superseded`) | |
| `verified_check_id` | uuid FK kyc_checks null | **traceability: the value links to its check** |
| `confirmed_by`, `confirmed_at` | text, timestamptz | the person who confirmed the auto-filled data |
| `created_at`, `created_by`, `updated_at`, `updated_by` | | |

- Unique: (`org_id`, `kind`, `value_hmac`) where `state` ≠ `superseded`.
- **Duplicate rule:** the same `value_hmac` verified under another org creates a `duplicate` check and a staff review. Two orgs never both hold a verified GSTIN.

### 2.4 `org_kyc_profile` (one row per org: the facts the app uses)
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid PK | |
| `legal_name`, `trade_name`, `constitution` | text | from the GST check, confirmed by the supplier; each has a `*_check_id` FK to `kyc_checks` |
| `registered_address` | jsonb | structured `{line1, line2, city, district, state, pincode, country}`; `address_check_id` |
| `display_city`, `display_state` | text | the only location shown to buyers before award |
| `kind_of_party` | text check in (`supplier`, `buyer_in`, `buyer_foreign`) | |
| `verification_hold` | bool default false | true while a sanctions `potential_hit` or `duplicate` review is open; RFQ send and invites check it |
| `kyc_state` | text check in (`not_started`, `in_progress`, `verified`, `needs_review`, `lapsed`, `withdrawn`) | a derived cache refreshed in code after every check or review; the badges themselves are always computed (§1.2) |
| `created_at`, `created_by`, `updated_at`, `updated_by` | | |

### 2.5 `org_signatories`
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | |
| `person_id` | uuid FK persons | the logged-in person claiming authority |
| `name_normalised` | text | as typed and confirmed |
| `role_claimed` | text check in (`proprietor`, `partner`, `director`, `designated_partner`, `karta`, `authorised_signatory`) | |
| `pan_ciphertext`, `pan_masked`, `pan_hmac` | | individual PAN; asked **only** when the name is not found in the register |
| `method` | text check in (`register_match`, `pan_match`, `authorisation_letter`, `staff`) | §5.3 |
| `state` | text check in (`pending`, `confirmed`, `rejected`) | |
| `check_id` | uuid FK kyc_checks | |
| `created_at`, `created_by`, `updated_at`, `updated_by` | | |

### 2.6 `bank_accounts`
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | |
| `account_ciphertext` | bytea | KMS, encryption context `{org_id, "bank_accounts", "account_number"}` |
| `account_last4` | char(4) | |
| `account_hmac` | char(64) | duplicate detection |
| `ifsc`, `bank_name` | text | |
| `holder_name_at_bank` | text | from the penny drop |
| `capture_method` | text check in (`typed`, `cheque_extracted`, `reverse_penny_drop`) | |
| `state` | text check in (`pending`, `verified`, `needs_review`, `failed`, `retired`) | one `verified` account per org at a time |
| `verified_check_id` | uuid FK kyc_checks null | |
| `razorpay_linked_account_id` | text null | **reserved for M2**; set when Route onboarding happens |
| `created_at`, `created_by`, `updated_at`, `updated_by` | | |

### 2.7 `kyc_documents`
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | |
| `doc_type` | text check in (`gst_certificate`, `cancelled_cheque`, `bank_statement_page`, `iec_certificate`, `udyam_certificate`, `authorisation_letter`, `foreign_registry_extract`, `other`) | |
| `s3_key` | text | `kyc/<org_id>/<doc_id>`, generated by the server; never the user's file name |
| `mime`, `size_bytes`, `sha256` | | `mime` is the **sniffed** type, not the declared one |
| `state` | text check in (`awaiting_upload`, `uploaded`, `rejected_type`, `extracted`, `confirmed`, `deleted`) | |
| `extraction_approval_id` | uuid FK approvals null | the doc_check proposal and its human decision |
| `linked_check_id` | uuid FK kyc_checks null | e.g. the `registry_doc` check for foreign buyers |
| `retain_until` | timestamptz | policy in §2.10 |
| `deleted_at`, `deleted_by` | | the object is deleted from S3 and the row kept as a tombstone |
| `created_at`, `created_by` | | |

### 2.8 `verification_reviews` (the staff review queue)
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | **the customer org under review**. Read only through `PlatformScope` on the admin host |
| `reason` | text check in (`name_mismatch`, `bank_name_mismatch`, `sanctions_potential_hit`, `signatory_unconfirmed`, `duplicate_identifier`, `doc_needs_confirmation`, `provider_error_persistent`, `gst_cancelled_or_suspended`) | |
| `check_ids` | uuid[] | the evidence |
| `document_ids` | uuid[] | |
| `state` | text check in (`open`, `approved`, `rejected`, `info_requested`) | |
| `decision_note` | text null | 10–500 characters, contact-pattern checked |
| `decided_by`, `decided_at` | | `person:<staff id>` |
| `sla_due_at` | timestamptz | `created_at` + 2 IST working days (Q11) |
| `created_at`, `created_by` | | `system:kyc` |

A staff decision writes a new `kyc_checks` row (`provider = inhouse`, `upstream_source = staff`, outcome `pass` or `fail`, `result = {review_id}`). Badges therefore still trace to a check record, and the check traces to the person and their reason.

### 2.9 Sanctions list data (platform org)
- **`screening_list_versions`**: `org_id` (platform), `list` in (`un_sc`, `ofac_sdn`, `ofac_cons`, `eu_fsf`, `in_mha_uapa`, `in_dgft_del`, `aggregate`), `source_url`, `fetched_at`, `published_at`, `sha256`, `entry_count`, `created_at`, `created_by` = `system:sanctions_ingest`.
- **`screening_list_entries`**: `org_id` (platform), `version_id`, `list`, `entry_ref` (the list's own id), `entity_type` (`person`, `entity`, `vessel`), `names[]` (normalised), `countries[]`, `dob_or_incorp` (text), `programs[]`, `created_at`, `created_by`. A GIN `pg_trgm` index on the names unnested into the side table `screening_names(entry_id, name_norm)`.
- When a new list version arrives, the old version's entries are deleted after it, because they are public data, not personal records of our users.
- **Who is screened:** every buyer org (legal and trade name), every supplier org, and the named signatories and directors held in `org_signatories` and in the CIN `result`.

**Notice files (not a table):** `services/api/app/modules/verification/notices/<locale>/<purpose>.v<N>.md`, with front matter `id`, `version`, `purpose`, `retention`, `processors[]` and `effective_on`. They are changed by PR only. The `consents` row stores the id, version and sha256.

### 2.10 Retention and deletion (DPDP; counsel confirms, Q8)
| Data | Kept while | Then |
| --- | --- | --- |
| Onboarding abandoned (never verified) | 90 days after last activity | documents, ciphertexts and `org_kyc_profile` address deleted; checks keep only type, outcome, date and provider reference |
| Active org: documents | until verified + 30 days, unless needed as evidence for a review or a staff-approved mismatch | deleted (tombstone row kept) |
| Active org: checks, registrations, bank (encrypted) | while the account is active | |
| Account closed or erasure request | — | documents and ciphertexts deleted at once; `org_kyc_profile` personal fields nulled; `kyc_checks` kept **minimised** (type, outcome, dates, `provider_ref`, `input_hmac`) for **N years** (proposed 5, Q8) as fraud and dispute evidence, unless counsel says otherwise; `consents` kept as long as the minimised checks + 1 year |
| Sanctions list data | latest version only | |
| `kyc_checks` of foreign buyers with potential hits | 5 years after decision (Q8) | minimised |

Purges run as a nightly job (`kyc_retention_purge`). It writes `kyc.retention_purged` with counts only, and it is the only code path that deletes KYC objects or rows.

### 2.11 Additive changes to earlier tables
- `provider_credentials` (E0b): seed rows `cashfree_verification` (kind `tool`, `api_key`, secret `orsyn/<env>/providers/cashfree_verification` holding `{client_id, client_secret}`) and `<secondary>_verification` if Q3 needs it. **E0b's `gst_lookup` slot is retired**, because the verification provider replaces it; `ai/tools/gst_lookup` becomes a thin wrapper over `verification.gstin()`. The secret `orsyn/<env>/kyc/hmac` holds the HMAC key and is not shown in admin.
- `approvals` (M1): new `kind = 'kyc_extraction'`, `payload = {doc_id, fields, confidence}`. The supplier's confirm or edit is the decision.
- `orgs` (E0c/E0d): no change; `orgs.status = suspended` is still a separate staff action.

---

## 3. API

Common rules:
- Customer routes are under `/v1`, with the customer auth from the login story, `org_id` taken from the session (never from the body), and the role checks below.
- Admin routes are under `/admin/v1` with E0b auth, CSRF and host rules, and `include_in_schema=False`.
- Errors use `{"error": {"code","message"}}`. Times are ISO-8601 UTC; the UI shows IST. Money is a string decimal plus `currency`.
- **Request and response bodies of every KYC route are excluded from request logging.**
- Rate limits: §3.5.

Roles (from the login story): `org_owner` can do everything for their org; `org_member` can read status only. Suppliers and buyers use the same routes, and `kind_of_party` decides the steps.

### 3.1 Supplier and Indian buyer: verification flow
| Method and path | Who | Request | Response | Errors |
| --- | --- | --- | --- | --- |
| `GET /v1/verification` | owner, member | | `{kyc_state, steps:[{key, state, due_at?, badge?}], badges:[§3.3 shape], recheck_due:[{check_type, due_at}], hold: bool}` | |
| `GET /v1/verification/notices/{purpose}?locale` | owner | | `{notice_id, version, sha256, markdown}` | 404 |
| `POST /v1/verification/consents` | owner | `{purpose, notice_id, notice_version, notice_sha256, granted: true}` | consent row (id, purpose, created_at) | 409 `stale_notice` (sha mismatch); 422 |
| `POST /v1/verification/consents/{purpose}/withdraw` | owner | `{}` | `{withdrawn_at, effects:[...]}`, e.g. "Bank verified badge removed; payouts will need a new consent" | 404 |
| `POST /v1/verification/gstin` | owner | `{gstin}` | `{check_id, outcome, prefill:{legal_name, trade_name, constitution, state, principal_address, display_city}, pan_masked, is_primary}` | 412 `consent_required`; 422 `gstin_invalid_checksum`; 409 `gstin_already_verified_elsewhere` (also opens a duplicate review; the other org is not named); 424 `gst_not_active` (status returned); 503 `provider_unavailable` |
| `POST /v1/verification/gstin/{check_id}/confirm` | owner | `{legal_name_confirmed: true, trade_name?: str}`. Only the trade name may be edited; the legal name is not editable (it must match GST) | `{org_kyc_profile}` and the derived PAN check started | 409 `already_confirmed` |
| `POST /v1/verification/registrations` | owner | `{kind: udyam\|iec\|cin\|llpin, value?}`. `value` may be omitted for `iec` (the PAN is tried) | check result | 412, 422 format, 424 `not_found`, 503 |
| `POST /v1/verification/signatory` | owner | `{name, role_claimed, pan?}`. `pan` only when the API asks for it with 409 `pan_needed` | `{state, method}` | 409 `pan_needed`; 202 `needs_review` |
| `POST /v1/verification/bank` | owner | `{account_number, ifsc, method: typed}` (both re-typed to confirm in the UI only) | `{state, account_last4, holder_name_at_bank, name_match}` | 412; 422 IFSC or account format; 424 `account_not_found`; 202 `needs_review` (name mismatch) |
| `POST /v1/verification/bank/reverse-penny-drop` | owner | `{}` | `{upi_intent_url, qr_png_data_url, expires_at}` (the provider's collect link) | 412; 503 |
| `POST /v1/verification/documents` | owner | `{doc_type, content_type, size_bytes}` | `{doc_id, upload: {url, fields}, expires_in: 300}` (S3 presigned POST with `content-length-range` 1–10 MB and an exact `Content-Type`) | 422 `type_not_allowed` (only `application/pdf`, `image/jpeg`, `image/png`); 413 |
| `POST /v1/verification/documents/{id}/complete` | owner | `{}` | `{state, extraction_approval_id?}`. The server runs HeadObject, sniffs the magic bytes, computes sha256, then enqueues `doc_check` | 422 `content_mismatch` (object deleted); 404 |
| `GET /v1/verification/documents/{id}` | owner | | `{doc_type, state, uploaded_at, download_url (60 s, attachment)}` | 404 (another org's document → 404, not 403) |
| `DELETE /v1/verification/documents/{id}` | owner | `{}` | `{deleted_at}`, allowed unless the document is evidence in an open review (409) | 409 |
| `POST /v1/approvals/{id}/decide` (M1, existing) | owner | `{decision, edited_fields?}` | | the KYC extraction confirm goes through the normal approvals route |
| `POST /v1/verification/data-requests` | owner, or any person for their own data | `{type: access\|correction\|erasure, note?}` | `{request_id, due_by}` | DPDP rights; opens a staff task (§3.4) |

### 3.2 Foreign buyer
| Method and path | Who | Request | Response | Errors |
| --- | --- | --- | --- | --- |
| `POST /v1/verification/foreign-business` | owner | `{legal_name, country (ISO-2), registry_number, registry_name?, website, address:{...}}` | `{kyc_state, checks:[domain, sanctions], next: "upload_registry_extract"}` | 412; 422 |
| Documents | same routes as §3.1 with `doc_type = foreign_registry_extract` | | | |

Sanctions screening and the domain check run **synchronously** on this call (they are in-house and fast). A `potential_hit` sets `verification_hold` and returns `kyc_state = needs_review`. The UI says "We're reviewing your details; this usually takes 2 working days." The **reason is never disclosed** (tipping-off hygiene, Q6).

**Domain check (SSRF-safe):**
- It does no fetching of page content. It uses DNS A/AAAA/MX lookups through the VPC resolver, an RDAP query to the IANA-bootstrapped registry (an allow-list of RDAP hosts), and an HTTPS HEAD to `https://<domain>/` with redirects off and a 3 s timeout, **refused when any resolved IP is private, loopback or link-local, or in the metadata ranges**.
- `email_domain_matches` compares the owner's login email domain with the website domain; free-mail domains count as a non-match.

### 3.3 Badges (buyer- and supplier-facing)
| Method and path | Who | Response |
| --- | --- | --- |
| `GET /v1/orgs/{id}/badges` | any signed-in customer | `[{badge, label, since, checked_on, recheck_by, sources:[{check_id, check_type, upstream_source, provider, checked_on, provider_ref_masked}]}]`. `provider_ref_masked` shows the last 6 characters. **No identifier values.** The badge detail says "GSTIN checked with GSTN via Cashfree on 05 Oct 2026, 14:32 IST; next check by 04 Nov 2026" |
| `GET /v1/orgs/{id}/badges/{badge}` | any signed-in customer | the same item |

The serializer for other orgs has **no fields** for GSTIN, PAN, legal name, street address or bank details. After award (M2), the PO serializer adds GSTIN and legal name for the counterparty on that PO only, sourced from `org_registrations` and `org_kyc_profile` with their `check_id`.

### 3.4 Admin (staff review queue, in the E0b/E0d console)
| Method and path | Who | Request | Response | Errors |
| --- | --- | --- | --- | --- |
| `GET /admin/v1/verification/reviews` | viewer, owner | `state?`, `reason?`, `org_id?`, `cursor` | `[{id, org_id, org_name, reason, state, created_at, sla_due_at}]` | |
| `GET /admin/v1/verification/reviews/{id}` | viewer, owner | | review + checks (masked inputs, `result`) + document list (no URLs) + the org's badge state + related consent state | 404 |
| `POST /admin/v1/verification/reviews/{id}/documents/{doc_id}/view` | **owner** | `{reason_code: kyc_review\|legal_request, note: 10–200}` | `{url (60 s, attachment), expires_at}` | 403 viewer; 409 doc deleted; 429 more than 30 per staff per day |
| `POST /admin/v1/verification/reviews/{id}/reveal` | **owner** | `{field: pan\|bank_account, reason_code, note}` | `{value, expires_at}` (15 minutes, the E0d reveal pattern) | 403; 429 |
| `POST /admin/v1/verification/reviews/{id}/decide` | **owner** | `{decision: approve\|reject\|request_info, note: 10–500, info_request_text?: str}` | review | 409 not open; 422 |
| `POST /admin/v1/verification/orgs/{id}/rescreen` | **owner** | `{reason}` | sanctions check | 429 (1 per org per 10 minutes) |
| `GET /admin/v1/verification/lists` | viewer, owner | | `[{list, version, published_at, fetched_at, entry_count, state}]` | |
| `GET /admin/v1/verification/data-requests` / `POST …/{id}/complete` | viewer / **owner** | `{note}` | | DPDP rights handling |
| `GET /admin/v1/verification/stats` | viewer, owner | IST range | `{started, verified, median_minutes_to_verified, reviews_open, reviews_by_reason, provider_calls, cost_by_check_type:[{check_type, amount, currency}]}` | |

`request_info` sends the supplier a **fixed-template** notification ("We need one more document: <doc type>") through the system notification channel. No agent drafts it and it carries no free text from the model. The staff `info_request_text` is shown only in-app, after a contact-pattern check.

### 3.5 Webhooks and limits
- `POST /webhooks/verification/{provider}`: for reverse penny drop completion and any asynchronous check.
  - It verifies the vendor signature (per vendor docs; ai-engineer confirms the header and algorithm), rejects timestamps more than 5 minutes old, and is idempotent on the vendor event id (unique index on `verification_webhook_receipts(provider, event_id)`, a small table with `org_id` = the resolved org or the platform org, `created_at` and `created_by = system:webhook`).
  - It enqueues to SQS and returns 200 quickly. The body is never logged.
- **Abuse and cost limits (per org, IST day):** GSTIN 10, PAN 5, bank 5, reverse penny drop 3, registrations 10, documents 20. Before signup is complete, WhatsApp GSTIN lookups are limited to 3 per number per day. Exceeding a limit → 429 `daily_limit`. The limits live in `policy.py`.
- **Kill switch:** the E0b `provider_credentials.enabled = false` makes every provider call return 503 `provider_unavailable`. Users see "Verification is paused; we'll message you when it's back", and a `kyc.provider_unavailable` event is written.

---

## 4. Events

The E0c/E0d shape is used, with `subject_type` = `org`, `kyc_check`, `review`, `document`, `consent` or `bank_account`. **Payloads never contain an identifier value, a name, an address, a contact or document text**: only ids, masked values, enums and outcomes. A test enforces this.

| Type | Actor | Source | Payload |
| --- | --- | --- | --- |
| `consent.granted` / `.withdrawn` | person | pwa / web / whatsapp | `{purpose, notice_id, notice_version}` |
| `kyc.started` | person | pwa / whatsapp | `{kind_of_party}` |
| `kyc.check_completed` | person or `system:kyc_recheck` / `system:sanctions_screen` | api / job | `{check_id, check_type, outcome, provider, upstream_source, cost_amount, currency}` |
| `kyc.check_failed` | same | same | `{check_type, error_code}` |
| `kyc.profile_confirmed` | person | pwa | `{check_id}` |
| `kyc.badge_granted` / `.badge_lapsed` / `.badge_revoked` | `system:kyc` | api / job | `{badge, check_ids, reason?}` (`lapsed` = expired, `revoked` = failed or withdrawn) |
| `kyc.state_changed` | `system:kyc` | api / job | `{from, to}` |
| `kyc.hold_set` / `.hold_cleared` | `system:kyc` / person (staff) | api / admin_ui | `{review_id}` |
| `kyc.document_uploaded` / `.rejected_type` / `.deleted` | person or `system:kyc_retention_purge` | pwa / job | `{doc_id, doc_type, size_bytes, mime}` |
| `kyc.extraction_proposed` | `agent:doc_check` | job | `{doc_id, approval_id, prompt_version, confidence}` |
| `approval.decided` (existing) | person | pwa | as the M1 approvals plan |
| `kyc.review_opened` | `system:kyc` | api / job | `{review_id, reason}` |
| `kyc.review_decided` | person (staff) | admin_ui | `{review_id, decision}`; the note is not copied into the event |
| `staff.kyc_document_viewed` / `staff.kyc_field_revealed` | person (staff) | admin_ui | `{review_id, doc_id or field, reason_code, expires_at}` |
| `sanctions.list_ingested` | `system:sanctions_ingest` | job | `{list, version_id, entry_count, delta_added, delta_removed}` |
| `sanctions.rescreen_completed` | `system:sanctions_screen` | job | `{orgs_screened, potential_hits}` |
| `kyc.provider_unavailable` | `system:kyc` | api | `{provider, check_type}`, first per provider per 15 minutes (also an E0d alert log line) |
| `kyc.webhook_received` | `system:webhook` | webhook | `{provider, event_type, verified: bool}` |
| `dpdp.request_opened` / `.request_completed` | person / staff | pwa / admin_ui | `{request_id, type}` |
| `kyc.retention_purged` | `system:kyc_retention_purge` | job | `{documents, ciphertexts, profiles}` (counts) |

---

## 5. AI agents

### 5.1 `doc_check` (existing agent): a new KYC extraction mode
- **Prompt file:** `services/api/app/ai/prompts/doc_check_kyc.md`, id `doc_check_kyc`, **version 1**, with a changelog.
- **Input:** one uploaded image or PDF page (at most 2 pages), plus `doc_type`. The document is delimited as data, and instructions inside it are ignored.
- **Output schemas** (Pydantic, one per `doc_type`; every field is `{value, confidence: 0–1, basis: "<page/region description>"}`; the overall `confidence` is the minimum over required fields):
  - `gst_certificate` → `{gstin, legal_name, trade_name}`
  - `cancelled_cheque` / `bank_statement_page` → `{account_number, ifsc, account_holder_name}`
  - `iec_certificate` → `{iec, firm_name}`
  - `udyam_certificate` → `{udyam_number, enterprise_name}`
  - `foreign_registry_extract` → `{company_name, registry_number, country, incorporation_date, registry_name, status_text}`
  - `authorisation_letter` → `{authorised_person_name, issuing_entity_name, signed_by_name, date}`
- **What the model never does:** it decides nothing (no pass or fail, no name-match judgement), computes nothing, and never reads or writes rules. It may return `null` with `confidence: 0`; abstaining is correct behaviour.
- **What code does after extraction:** format and checksum validation (§1.3). A failed checksum sets the field confidence to 0 and asks the user to type it.
- **Approval point:**
  - For Indian documents, the extraction becomes an `approvals` row (`kind = kyc_extraction`). The supplier sees the fields **pre-filled and editable** and taps "Use these". Only then does the deterministic API check run, so the API, not the model, confirms the fact.
  - For `foreign_registry_extract` and `authorisation_letter` there is no API, so a **staff owner** confirms in the review queue against the document.
- **Routing and residency:** feature `kyc_doc_check`. KYC documents carry identity data, so the route is the **Haiku-role model on the India geo profile (`in.`)**, which keeps processing in India.
  - There is **no Global Sonnet or Opus fallback**. Low confidence (< 0.85 on any required field) falls back to the person typing or staff, not to a bigger model outside India.
  - ai-engineer confirms that the India-profile model reads these documents well enough on the eval (§8.3). If it does not, this becomes founder question Q4: accept Global for KYC docs, or drop extraction.
- **Personal data sent to the model:** only the document the user uploaded for that purpose. Masking is not possible on an image; that is why the route is India-resident. The model output is stored only in the `approvals` payload. The account number in a cheque extraction is moved to `bank_accounts.account_ciphertext` on confirm, and the approval payload keeps only the masked form after decision.

### 5.2 No other agent
- Name matching, sanctions matching, badge logic, the domain check and re-check scheduling are all **code**. No model explains sanctions hits.
- The AST assistant (if built) may read `GET /v1/verification` for "what's left to verify?". It must not prefill KYC fields; they are already on its never-list (AST §5.4: GSTIN, legal name, bank).

### 5.3 Signatory confirmation (deterministic, no agent)
1. **Register match:** the person's typed name, normalised, is matched against the names in the GST check (proprietor or partners, where the provider returns them) or the CIN/LLPIN directors and partners. A `high` match → `confirmed`.
2. **PAN match** (for proprietorships, the business PAN *is* the proprietor's PAN, so this usually passes at step 1): when no register name is available, ask for the person's PAN, run the PAN check, and require a name match `high` with the typed name **and** with a register name. Otherwise go to 3.
3. **Authorisation letter:** upload it on letterhead; doc_check extracts the names; a staff owner confirms.

---

## 6. Rules

Read from `packages/rules` (rules-curator adds them if missing, with primary sources, label `rules-change`):

| Rule id (proposed) | Layer | Used for | Primary source to open |
| --- | --- | --- | --- |
| `in-iec-required` | 1 | the "Export-ready" badge explanation and the roadmap step "Get an IEC" when the IEC check is `not_found` | DGFT, Foreign Trade Policy (IEC chapter) |
| `in-iec-annual-update` | 1 | the IEC re-check date is set after the annual update window, and the roadmap shows "Update your IEC" when `last_updated_on` is before the window | DGFT trade notice on annual IEC updation |

- Badge thresholds, re-check intervals, rate limits and name-match thresholds are **product policy in `policy.py`**, not export rules. They are never in a prompt.
- The doc_check prompt contains no requirement text (for example "IEC is mandatory").
- `schema.json` has only `status_logic: always_todo`. The IEC roadmap status driven by a check result needs a new value `iec_check`. rules-curator describes it, and backend adds it in PR 6.

---

## 7. Screens

`docs/screens.md` is a stub, so frontend builds to this section and `.claude/agents/frontend.md`; the founders add these screens to `screens.md` (Q14). The supplier side is the mobile-first PWA at 390px: one question per screen, large targets, numeric keyboards for numbers, and GSTIN and IFSC inputs auto-uppercase. Light theme; no gradients, emoji, sparkles or "AI-powered" copy. Strings are in English and Hindi. GSTIN, PAN, IFSC and Udyam values are never translated and are shown in IBM Plex Mono. Times show as `05 Oct 2026, 14:32 IST`.

### 7.1 Supplier PWA: `/s/verify` (stepper; resumes at the first incomplete step)
| Step | Holds | Empty | Loading | Error |
| --- | --- | --- | --- | --- |
| 1 **Consent** | Plain-language notice (purpose, what we check, with whom: "GSTN, Income Tax, MCA, DGFT, Udyam via our verification partner Cashfree", retention, your rights, grievance contact), "I agree" button, link to the full notice | n/a | skeleton text | "Couldn't load the notice." + Retry |
| 2 **GSTIN** | One input (15 characters, live checksum hint "This GSTIN doesn't look right" before any call) **or** "Take a photo of your GST certificate" | — | "Checking with GST…" (spinner, up to 10 s) | inline: invalid checksum; not active ("GST shows this registration as Cancelled. Contact us."); already linked ("This GSTIN is already linked to another account. We'll look into it."); provider down ("Verification is paused. We'll message you when it's back.") |
| 2b **Photo → fields** | The extracted GSTIN pre-filled and editable, "Use this" button | — | "Reading your certificate…" | "Couldn't read it. Please type the GSTIN." |
| 3 **Is this your business?** | Legal name, trade name (editable), constitution, address (read-only, from GST), "Yes, this is us" / "No" (→ contact support) | — | — | — |
| 4 **You are…** | Name (prefilled from the login), role chips (Proprietor / Partner / Director / Authorised signatory). If needed: PAN input, or "Upload authorisation letter" | — | "Checking…" | "We couldn't match your name. Upload a letter, or we'll review it within 2 working days." |
| 5 **More registrations** (optional) | Udyam toggle and number; "Do you export? We'll check your IEC" (one tap, uses the PAN); CIN/LLPIN shown only for companies and LLPs, prefilled if the provider returns it | "Skip for now" | per item | per item, inline |
| 6 **Bank account** (can be done later; required before payouts) | Two options: **"Pay ₹1 from your business account by UPI"** (reverse penny drop; nothing to type; refunded per the provider's flow, Q12) or **type the account number twice + IFSC** (bank name shown from the IFSC); or photo of a cancelled cheque → confirm fields | "Do this later" | "Verifying with your bank…" | name mismatch: "Your bank shows the name as R*** E*********. We'll review it within 2 working days." (masked to first letters); not found: "The bank couldn't find this account." |
| 7 **Done / status** `/s/verify/status` | Badge list with state (Verified, In review, Due for re-check on <date>, Lapsed), "What's due" list, documents (view or delete), consents (withdraw), "Download my data" / "Delete my data" requests | "Start verification" | skeleton | "Couldn't load your verification." + Retry |

### 7.2 WhatsApp (after the WhatsApp story; fixed templates only, no model)
1. "Send your GSTIN to verify your business."
2. The supplier sends the GSTIN, or a photo, which takes the doc_check path. Before any lookup, a consent message with a link to the notice and **Agree** / **Not now** quick-reply buttons; the tap is recorded as consent with `wa_message_id`.
3. "We found: **<legal name>**, <city>, <state>. Is this your business?" with Yes / No buttons.
4. "Finish in 1 minute: <signed deep link to /s/verify, 24 h, single use>" for signatory, bank and documents.

Bank numbers and documents are never requested in chat. Inbound bank numbers or documents in chat get a fixed reply pointing to the link, and are not stored (the webhook handler drops media of unknown purpose).

### 7.3 Buyer side
| Screen | Holds | Empty | Loading | Error |
| --- | --- | --- | --- | --- |
| **Badges** on the supplier card, quote comparison and showcase page | Badge chips (text and icon, no colour-only meaning). Tap → **Badge detail** sheet: what was checked, upstream source, provider, checked on, next check by. No identifier values | "Verification in progress" in muted text (or nothing, Q2) | — | the chip area hides; the card still renders |
| **Buyer verification** `/b/verify` | Indian: consent → GSTIN → confirm (same components). Foreign: consent → company name, country, registry number, website → upload registry extract → status | — | as above | as above; foreign hold: "We're reviewing your details; this usually takes 2 working days." |

### 7.4 Admin console (E0b/E0d route group): side panel item **Verification**
| Screen | Holds | Empty | Loading | Error |
| --- | --- | --- | --- | --- |
| **Queue** `/admin/verification` | Filters (reason, state, org). Table: org, reason, opened, SLA due (warn when past), state | "No reviews waiting." in ok colour | skeleton rows | error + Retry |
| **Case** `/admin/verification/[id]` | Org card (masked); checks timeline (type, outcome, source, provider ref, checked on); side-by-side names (GST legal name vs name at bank vs typed name) with the match level; documents (owner: **View** with a reason dialog → opens in a new tab for 60 s); sanctions candidates (list, entry ref, matched name, score, programmes; a link to the official list entry); decision form (Approve / Reject / Request info, note required) | n/a | skeleton | inline per action; 409 shown |
| **Lists** `/admin/verification/lists` | Each list: version, published, fetched, entries, state (stale > 48 h in warn) | "No lists loaded. Screening is off." in bad colour | skeleton | error + Retry |
| **Data requests** `/admin/verification/requests` | DPDP requests with due dates | "No open requests." | skeleton | error + Retry |
| **Stats** card on the E0d Overview | started / verified / median minutes / reviews open / provider cost MTD by check type | "No verifications yet." | skeleton | per card |

Accessibility as E0b: real buttons, labelled inputs, 44px targets, 4.5:1 contrast, and the stepper announced by screen readers.

---

## 8. Tests and evals (qa-evals; api tests in `services/api/tests/`, web tests in `apps/web/tests/`)

All provider calls use `FakeVerificationProvider` or `httpx.MockTransport`; KMS uses `botocore.stub.Stubber`; S3 uses moto or a Stubber; `pytest-socket` stays on (E0b). Fake-provider fixtures use **synthetic identifiers**: GSTINs with a valid checksum built on PANs from a reserved fake range listed in the fixture README. No real taxpayer's data is used.

### 8.1 One test per "Done when" clause
| Clause | Test |
| --- | --- |
| (a) GSTIN in → auto-fill | `test_gstin_prefills_profile`: a fake GST response → the `prefill` fields equal the allow-listed fields; confirm writes `org_kyc_profile` with a `*_check_id` per field; a PAN check is started from the GSTIN's characters 3–12 with no PAN input. `test_gstin_checksum_rejected_before_call` (0 provider calls, 0 cost). `test_whatsapp_gstin_flow` (after the WhatsApp story): GSTIN text → consent buttons → confirm → deep link; no bank prompt in chat |
| (b) consent first; withdrawal stops checks | `test_no_check_without_consent` (412, 0 provider calls) for each check route and for the re-check job. `test_consent_records_notice_version_and_channel`. `test_withdraw_stops_rechecks_and_revokes_badges`: after withdrawal, the scheduler skips the org; badges depending on that purpose → `kyc.badge_revoked`. `test_stale_notice_rejected` (sha mismatch → 409) |
| (c) check records; no Aadhaar | `test_every_check_writes_record` (parametrised over all check types): `upstream_source`, `checked_at`, `provider_ref`, `response_sha256`, `recheck_due_at` and Decimal `cost_amount` are set. `test_raw_response_never_persisted`: a sentinel field in the fake response (e.g. `taxpayer_mobile`) is absent from every DB column, log record, event and API response. `test_no_aadhaar_anywhere`: a scan of all request schemas has no Aadhaar field; any 12-digit Verhoeff-valid number in any request body → 422 `aadhaar_not_accepted`; a caplog and DB scan finds none |
| (d) badges only, traced, lapse; buyer cannot see KYC data | `test_badge_traces_to_checks`: every badge returned has ≥1 `check_id`, and each id exists with `outcome = pass` and is unexpired. `test_badge_lapses_on_expiry` (frozen time past `expires_at` → the badge is gone and `kyc.badge_lapsed` is written once). `test_badge_revoked_on_failed_recheck`. `test_buyer_view_has_no_kyc_fields`: a buyer's GET of the supplier card, showcase, quote comparison and badges responses, scanned for the supplier's GSTIN, PAN, legal name, street line, account last4 and IFSC → none found before award |
| (e) staff review queue | `test_mismatch_opens_review` for each reason. `test_only_owner_decides` (viewer → 403). `test_decision_writes_staff_check_and_event` (a new `kyc_checks` row with `provider = inhouse`, `upstream_source = staff`; badge recomputed). `test_note_required_and_contact_checked` |
| (f) buyer screening and hold | `test_foreign_buyer_screened_at_signup` (list fixture with a planted name). `test_potential_hit_sets_hold_and_blocks_rfq_send`: RFQ send → 409 `verification_hold`; supplier invites are not created. `test_rescreen_on_list_change`: ingesting a new version with an added entry that matches an existing buyer → a review opens. `test_weekly_rescreen_schedule` (the job runs over all orgs; idempotent). `test_hold_reason_not_disclosed` (customer response has no list name or score) |
| (g) uploads | `test_presigned_post_conditions` (content-length-range ≤ 10 MB, exact content type, 300 s, server-generated key under the org prefix). `test_complete_sniffs_magic_bytes` (an HTML file declared as PDF → deleted and `rejected_type`). `test_download_url_60s_attachment`. `test_extraction_requires_confirmation`: no API check runs and no `org_registrations` row is written until the approval is decided. `test_foreign_registry_needs_staff` |
| (h) re-checks | `test_recheck_scheduler_picks_due` (frozen time; consent required; rate limited per provider). `test_supplier_sees_due_list`. `test_gst_cancelled_on_recheck_drops_badges_and_opens_review` |
| (i) fake provider, secrets, cost | `test_fake_is_default_and_refused_in_prod` (settings validator). `test_provider_key_only_in_secret_store` (E0b scan pattern extended to the verification slot). `test_cost_logged_per_call` (Decimal from `prices.py`, `feature = kyc_<type>`). `test_kill_switch_returns_503_no_call`. `test_doc_check_cost_in_model_calls` (`feature = kyc_doc_check`) |
| (j) Razorpay mapping | `test_route_payload_from_stored_records`: from a verified fixture org, `build_route_linked_account_payload(org_id)` returns every required field in Appendix C, each with a `source_check_id`, and the stakeholder and settlement parts. It makes **no network call**, and it raises `MissingForRoute([...])` naming the gaps when a field is missing (e.g. bank not verified) |

### 8.2 Negative tests (always)
- **Masking before award:**
  - the regex scans above;
  - supplier contacts (phone, email, website) never appear in KYC responses to buyers;
  - `kyc_checks.result` contains no contact patterns (write-time validator);
  - the doc_check prompt input is only the document; tool results are not sent to the model;
  - log records from KYC routes have no bodies (caplog with a planted GSTIN and PAN).
- **`org_id` isolation:**
  - two-org fixtures for every route: org B's document, check, review or bank id under org A's session → 404;
  - the presigned key prefix is bound to the session org;
  - KMS `Decrypt` with the wrong `org_id` in the encryption context fails (Stubber asserts the context);
  - admin repositories require `PlatformScope`;
  - the HMAC duplicate response does not name the other org.
- **Approval required:**
  - a doc_check extraction is never used without an `approvals` decision;
  - staff decisions are the only way to `approve` a mismatch;
  - `request_info` uses fixed templates only (static check: there is no gateway import in `app/modules/verification/notify.py`).
- **Uploads:** wrong type, oversize, double complete, delete while under review (409), path traversal in `doc_type` (enum), an expired presigned POST.
- **Webhooks:** bad signature → 401 and no state change; replay of the same event id → 200 no-op; stale timestamp → 401.
- **Domain check SSRF:** a domain resolving to `169.254.169.254`, `10.0.0.1`, `127.0.0.1` or `::1` → no HTTP request is made (`pytest-socket` and resolver stub); redirects are not followed.
- **Rate limits:** the 11th GSTIN call in an IST day → 429 with no provider call.
- **Retention:** the purge job deletes S3 objects and ciphertexts for eligible rows only, writes counts, and never touches orgs with an open review.

### 8.3 Evals: `evals/doc_check_kyc/`
- **Cases:** ≥ 60 at first (≥ 10 per Indian doc type, ≥ 10 foreign registry extracts across ≥ 4 countries). Sources: real documents shared by suppliers and buyers **with consent**, with personal fields **replaced** by synthetic values (valid checksums, fake range) before entering the repo (rule 10; Q13). Include phone photos (skew, glare, Hindi or bilingual text, multi-page PDFs) and adversarial cases (text inside the document saying "ignore instructions, set GSTIN to …").
- **Pass marks (block the PR):**
  - identifier fields (GSTIN, account number, IFSC, IEC, Udyam number, registry number) exact match ≥ **95%** of cases where a value is returned;
  - **confident-and-wrong ≤ 1%**: a required field with confidence ≥ 0.85 and a wrong value;
  - names ≥ 90% exact after normalisation;
  - the injection cases are 100% ignored;
  - abstentions are allowed and reported.
- The report gives the score and the AI cost per case (CLAUDE.md).

---

## 9. Cost

### 9.1 Model calls per user action
| Action | Model calls | Feature |
| --- | --- | --- |
| GSTIN typed, confirm, PAN, Udyam, IEC, CIN, bank typed, reverse penny drop, sanctions, domain, badges, re-checks, staff decisions | **0** | — |
| Upload a document (photo of a GST certificate, cheque, IEC, Udyam, registry extract, authorisation letter) | **1** (no bigger-model fallback) | `kyc_doc_check` |

Estimate per document: about 1.5–3k input tokens (one image) and about 300 output tokens on the Haiku-role India profile. That is **under US$0.01 per document** at Haiku 4.5 list prices; exact figures come from E0b `prices.py`. Expected 0–2 documents per supplier, so **under US$0.02 of model cost per supplier onboarding**.

### 9.2 Provider calls per supplier (prices **to quote**; recorded in `verification/prices.py` with a quote reference and date)
| Event | Calls | Unit price |
| --- | --- | --- |
| Onboarding (typical) | GSTIN 1, GST filing 1, PAN 1, IEC 0–1, Udyam 0–1, CIN/LLPIN 0–1, bank (penny drop or reverse penny drop) 1, name match 0–1 → **4–8 calls** | to quote per check type |
| Re-checks, year 1 | GSTIN 12 (monthly), GST filing 12, PAN 1, IEC 1, Udyam 1, CIN 2, bank 0–1 → **≈ 28 calls** | to quote |
| Foreign buyer | 0 provider calls (in-house sanctions and domain); RDAP and DNS are free | — |

**Cost per verified supplier = Σ(calls × quoted unit price), computed in code and shown in admin Stats.** The founder should ask for per-check-type INR prices, monthly minimums, sandbox access, data-residency (India) and DPA terms in each quote (Q3). Re-check frequency is the main cost lever, and it is set in `policy.py` (Q2).

### 9.3 Infra, monthly per environment (AWS list prices; infra confirms)
- 1 KMS customer-managed key `orsyn-<env>-pii`: US$1. Requests at US$0.03 per 10k: under US$0.10.
- Secrets Manager: 2 new secrets (verification provider, HMAC key) × US$0.40 = US$0.80 (+1 if there is a secondary provider).
- S3 `orsyn-<env>-kyc` (SSE-KMS with the CMK, Bucket Keys on): pennies at Phase 1 volume.
- EventBridge Scheduler (nightly ingest, re-checks, retention purge, weekly re-screen): within the free tier.
- Sanctions data:
  - **US$0** if we ingest the official lists ourselves (UN, OFAC and EU are free downloads; the India MHA list is a web page or PDF that needs a parser and a manual check, Q5);
  - an aggregator licence (e.g. OpenSanctions commercial) is **to quote**.
- **Expected ≈ US$2–3 (≈ ₹170–255 at an assumed ₹85/US$) per environment, excluding provider per-call fees and any list licence.**

---

## 10. PR split

**Prerequisites:**
- E0c: `orgs`, `events`.
- E0b PRs 1–5: `provider_credentials`, `SecretStore`, admin auth, gateway with `in.` routing.
- The **customer login story**, with `persons` and org roles.
- The **M1 `approvals` table**.
- E0d PR 1 if the admin web reuses its shell.
- WhatsApp parts wait for the WhatsApp webhook story.

**Suggested split into sub-stories (Q1):**
- **KYC-1** Indian supplier KYB + badges + review queue (M1, blocks "verified" in matching).
- **KYC-2** Bank verification (M1 build, required before M2 payouts).
- **KYC-3** Buyer verification + sanctions (M1 for foreign buyers).
- **KYC-4** Route handover (M2, in the payments story).

| # | Sub-story | PR | Builder(s) | ~Lines | Labels |
| --- | --- | --- | --- | --- | --- |
| 1 | KYC-1 | Migration A (reversible): `consents` (+ append-only trigger), `kyc_checks` (+ trigger), `org_registrations`, `org_kyc_profile`, `org_signatories`, `verification_reviews`; `provider_credentials` seed rows; `approvals.kind` value; repositories with the `org_id` and `PlatformScope` guards; tests | backend, qa-evals | ~390 | needs-founder, security-review |
| 2 | KYC-1 | KMS field-encryption helper (encryption context, Stubber tests), HMAC helper (key from SecretStore), format validators (GSTIN checksum, PAN, IFSC, Udyam, CIN/LLPIN, IEC, Aadhaar-shaped reject), name normaliser and matcher; tests | backend, qa-evals | ~350 | needs-founder, security-review |
| 3 | KYC-1 | `app/ai/tools/verification/`: `VerificationProvider` Protocol (one method per check type returning a typed normalised result + `provider_ref` + `response_sha256`), routing table per check type, `FakeVerificationProvider`, `prices.py` (rows to-quote and blank until contracted; a test allows `fake` only), allow-list normalisation and contact-field dropping, kill-switch and spend logging into `kyc_checks`; `gst_lookup` re-pointed; tests | ai-engineer, qa-evals | ~390 | security-review |
| 4 | KYC-1 | Primary adapter (Cashfree, pending Q3) for GSTIN, PAN, name match, PAN→GSTIN; MockTransport tests from the vendor's documented examples; secret-shape and header redaction | ai-engineer, qa-evals | ~330 | needs-founder (spend), security-review |
| 5 | KYC-1 | Secondary checks adapter(s): GST filing, Udyam, IEC, CIN/LLPIN (provider per Q3); tests | ai-engineer, qa-evals | ~320 | needs-founder (spend), security-review |
| 6 | KYC-1 | `policy.py` (badges, intervals, limits, thresholds), badge computation, `kyc_state` derivation, `iec_check` status logic for the rules engine; tests | backend, qa-evals | ~330 | |
| 7 | KYC-1 | rules-curator: `in-iec-required`, `in-iec-annual-update` with DGFT sources; schema enum `iec_check` (described to backend in PR 6); `docs/rules-table.md` | rules-curator | ~120 | rules-change |
| 8 | KYC-1 | Supplier API: status, notices, consents and withdraw, GSTIN and confirm, registrations, signatory, data requests; rate limits; body-log exclusion; tests | backend, qa-evals | ~400 | needs-founder (PII), security-review |
| 9 | KYC-1 | Documents: presigned POST, complete (HeadObject, magic-byte sniff, sha256), view and delete, SQS enqueue of `doc_check`; `kyc_documents` migration; tests | backend, qa-evals | ~380 | needs-founder, security-review |
| 10 | KYC-1 | `doc_check_kyc` v1 prompt, per-type schemas, checksum post-validation, `approvals` proposal, routing `kyc_doc_check` → `in.` Haiku-role; `evals/doc_check_kyc/` cases + runner report | ai-engineer, qa-evals | ~400 | security-review |
| 11 | KYC-1 | Admin API: review queue, case, decide, document view and field reveal with reason, stats; tests | backend, qa-evals | ~380 | security-review |
| 12 | KYC-1 | Jobs: re-check scheduler, badge lapse, `kyc_retention_purge`, supplier "due" notifications (fixed templates); tests | backend, qa-evals | ~360 | needs-founder (deletion), security-review |
| 13 | KYC-1 | Web PWA: `/s/verify` steps 1–5 + status page, shared stepper components, Hindi strings; tests | frontend, qa-evals | ~400 | |
| 14 | KYC-1 | Web: buyer badge chips and badge detail sheet; admin Verification queue, case and data requests; tests | frontend, qa-evals | ~390 | security-review |
| 15 | KYC-2 | `bank_accounts` migration; bank API (typed, cheque-extracted), reverse penny drop start; webhook endpoint + `verification_webhook_receipts`; bank adapter methods; tests | backend, ai-engineer, qa-evals | ~400 | needs-founder, security-review |
| 16 | KYC-2 | Web PWA step 6 (UPI ₹1 / type / cheque photo) and the bank badge; tests | frontend, qa-evals | ~280 | |
| 17 | KYC-3 | Sanctions: list version and entry migration, ingest jobs per list (UN XML, OFAC, EU; India MHA parser or aggregator per Q5), `pg_trgm` matcher with normalisation, screen on signup, re-screen on change and weekly, hold enforcement hook for RFQ send; tests | backend, qa-evals | ~400 | needs-founder, security-review |
| 18 | KYC-3 | Foreign buyer API + SSRF-safe domain check (DNS, RDAP allow-list, HEAD with IP guard) + registry doc review path; Indian buyer GSTIN path reuse; tests | backend, qa-evals | ~350 | security-review |
| 19 | KYC-3 | Web: `/b/verify` (Indian and foreign), hold state, admin Lists page; tests | frontend, qa-evals | ~330 | |
| 20 | KYC-1/3 | Infra: KMS CMK + key policy (api role Encrypt/Decrypt with an encryption-context condition), S3 `orsyn-<env>-kyc` (BPA, SSE-KMS, TLS-only policy, no versioning, CORS for the PWA origin, POST only), secrets placeholders, IAM (`s3:PutObject`/`GetObject`/`DeleteObject` on the `kyc/*` prefix, `kms:*` scoped), schedules, VPC egress for the provider hosts, alarms on `kyc.provider_unavailable` and stale lists, cost note | infra | ~320 | needs-founder, security-review |
| 21 | KYC-1 | WhatsApp onboarding templates and handler (after the WhatsApp story): GSTIN text or photo, consent buttons, confirm, signed deep link; tests | backend, qa-evals | ~300 | needs-founder (login path: deep link), security-review |
| 22 | KYC-4 (M2) | `build_route_linked_account_payload()` + `MissingForRoute` + the `payouts_share_with_razorpay` consent notice; mapping test only, no Razorpay call | backend, qa-evals | ~200 | needs-founder, security-review |

**Order:**
- 1 → 2 → 3 → 4/5 (parallel) → 6 → 8.
- 7 is parallel with 6.
- 9 after 2; 10 after 3 and 9; 11 after 8; 12 after 6 and 8.
- 13 after 8 and 10; 14 after 11.
- 15 after 4; 16 after 15.
- 17 after 1; 18 after 17; 19 after 18.
- 20 is reviewed alongside and merges before any real provider use.
- 21 after the WhatsApp story; 22 in M2.

**File ownership** (no overlap):
- backend: `app/modules/verification/**`, `app/admin/verification/**`, `app/jobs/kyc_*`, `app/security/{kms,hmac}.py`, migrations.
- ai-engineer: `app/ai/tools/verification/**`, `app/ai/agents/doc_check*`, `app/ai/prompts/doc_check_kyc.md`, `app/ai/routing.py`.
- frontend: `apps/web/app/(supplier)/s/verify/**`, `apps/web/app/(buyer)/b/verify/**`, `components/badges/**`, `app/(admin)/admin/verification/**`.
- rules-curator: `packages/rules/**`, `docs/rules-table.md`.
- infra: `infra/**`.
- qa-evals: tests and `evals/doc_check_kyc/**`.
- No new Python dependency: `pg_trgm` is a Postgres extension enabled in migration 17, and `httpx` and `boto3` already exist.

---

## 11. Flags

- **needs-founder: yes.**
  - **Migrations:** about 10 new tables, triggers and an extension.
  - **Personal data:** PAN, bank accounts, signatory names, consent records, and DPDP retention and deletion jobs.
  - **Secrets:** the verification provider keys and the HMAC key.
  - **Spend:** a paid provider contract, per-call fees and possibly a list licence.
  - **Login path:** the WhatsApp signed deep link.
  - **Approval paths:** the new `kyc_extraction` approvals kind and staff decisions.
  - **Data residency:** the KYC doc route stays India-only.
- **security-review: yes.**
  - **Uploads:** presigned POST, sniffing, URL lifetime.
  - **PII and masking:** buyer serializers, log exclusion, adapter allow-lists, staff reveal.
  - **Isolation:** two-org tests, KMS encryption context, `PlatformScope`.
  - **Webhooks:** signature, replay, idempotency.
  - **IAM and KMS:** key policy and S3 prefix scoping.
  - **Outbound fetch:** SSRF guard on the domain check.
  - **Secrets:** handling of the provider keys and the HMAC key.
  - **Payments:** payment-adjacent bank data, and the KYC-4 payload.
- **rules-change: yes** (PR 7: IEC rules and the `iec_check` status logic).
- Milestone labels: **M1** for KYC-1/2/3; **M2** for KYC-4.

---

## 12. Open questions

1. **Story key, split and "Done when".** Is `KYC` the right key, with sub-stories KYC-1…4? Confirm the proposed "Done when" in §1.1. Is KYC-1 a blocker for M1's "first RFQ loop" (only verified suppliers invited), or can unverified suppliers quote with a visible "Verification in progress"?
2. **Verification policy.** Confirm:
   - the composite "Verified supplier" (GST + PAN + signatory + screening; bank only before payout);
   - re-check intervals: GST monthly, PAN yearly, IEC yearly after the update window, Udyam yearly, CIN six-monthly, sanctions on list change + weekly;
   - whether "GST returns filed" is shown, and how: as a fact on the GST badge detail (proposed), not a pass or fail;
   - whether buyers see "Verification in progress" or nothing for unverified suppliers.
3. **Provider.** Approve **Cashfree Secure ID as primary** (public docs; covers GSTIN, PAN, bank and reverse penny drop, name match and DigiLocker; RBI-regulated parent, which helps the processor due diligence) and get quotes from **Surepass and Perfios/Karza** for GST filing status, Udyam, IEC and CIN/LLPIN, plus IDfy and Signzy as alternatives. Ask each for:
   - INR price per check type;
   - minimum commitment;
   - sandbox access;
   - India data residency and storage period;
   - a DPA;
   - webhook signing;
   - whether they return taxpayer contact data (we drop it).

   If one provider covers everything at a fair price, use one.
4. **Model residency for KYC documents.** Keep `kyc_doc_check` on the India-only Haiku-role profile with no Global fallback (recommended)? If its eval misses the pass marks, choose between allowing Global Sonnet for KYC documents (disclosed in the notice) and dropping photo extraction (users type).
5. **Sanctions data.** Ingest the official lists ourselves (free; the India MHA UAPA schedules and the DGFT denied-entity list need a parser and a manual check) or license an aggregate dataset (to quote)? Which lists exactly: UN SC, OFAC SDN + non-SDN, EU FSF, UK, India MHA, DGFT? Also BIS Entity List for US-linked buyers? And screen Indian suppliers and their directors too (proposed yes)?
6. **Sanctions hold policy.** Is "hold RFQs, no reason disclosed, staff decide in 2 working days" right? Who at Orsyn may clear a potential hit: any owner, or only a named compliance owner (Nithish)? Is a second owner needed for a true-match block?
7. **Aadhaar.** Confirm **no Aadhaar in KYC-1…4**. If some proprietors have no register name match and no PAN match, is the authorisation letter + staff review enough, or do you want DigiLocker (PAN document pull) as a self-serve path?
8. **DPDP and retention (counsel).**
   - Minimised check records kept 5 years after closure?
   - Documents deleted 30 days after verification?
   - Abandoned onboarding purged at 90 days?
   - Consent logs kept for the minimised-record period + 1 year?
   - Is sanctions screening covered by notice as a legitimate use, or by consent?
   - Who is the grievance officer?
   - What is the breach runbook owner and the 72-hour report path?
   - Which processors go in the notice: AWS, Cashfree, a secondary provider, Meta, and Razorpay (M2)?
9. **Malware scanning of uploads.** Add GuardDuty Malware Protection for S3 on the KYC bucket (per-GB list price, to confirm) now, or rely on type sniffing + attachment downloads until volume grows?
10. **Display before award.** Proposed: buyers see badges + city/state only; GSTIN, legal name and street address only after award. Does the showcase page already show the trade name? Trade name is allowed (proposed), legal name is not; please confirm.
11. **Review SLA and staffing.** Is 2 IST working days right? Who works the queue in M1 (the founders)? Should an email alert go out when a review passes its SLA (E0d info topic)?
12. **Reverse penny drop.** Offer UPI ₹1 as the default bank method (no typing; it proves the payer controls the account)? Who bears the ₹1, and is it refunded (provider-dependent)? Note that it captures the account the supplier paid from, which must be the business account. We name-match it to GST and review mismatches.
13. **Eval fixtures.** Can we collect 60 consented KYC documents from early suppliers and buyers, with identifiers overlaid with synthetic values, under rule 10? Who collects them and records consent?
14. **`docs/screens.md`.** Who adds the verification screens? Do you want a mobile sketch of `/s/verify` before PR 13?
15. **Multi-GSTIN suppliers.** Verify only the primary GSTIN (proposed), or every state registration the supplier ships from (which matters for e-invoicing and e-way bills in M2)?

---

## Appendix A: Orsyn's own business KYC (founder checklist, not code)

**Company**
- [ ] Incorporation (Pvt Ltd or LLP): PAN, TAN, a current account in the company name.
- [ ] GST registration. Ask the CA whether Orsyn is an **e-commerce operator** for M2 payments flows; if so, TCS under CGST s.52 may require registration regardless of turnover.
- [ ] IEC only if Orsyn itself will be the exporter of record (M4 model question).
- [ ] Udyam (optional; it may help with banks and government programmes).
- [ ] Trademark search for the final name.

**Payments: Razorpay**
- [ ] Merchant account KYC: company documents, director details, bank, and a live website with terms, privacy, refund and cancellation, and a contact page.
- [ ] Ask Razorpay to enable **Route** for a B2B marketplace and confirm whether the business model needs its review. Get written confirmation of who does linked-account KYC (Razorpay does its own; we pre-fill from KYC-4).
- [ ] Confirm whether RazorpayX "fund account validation" is needed at all, given we verify banks through the KYC provider.

**WhatsApp: Meta**
- [ ] Meta Business Manager **business verification**: legal name, address, phone, website, domain verification, and a document such as a GST certificate or incorporation certificate.
- [ ] WhatsApp Business Account: display name approval, a dedicated phone number, a message template approval plan (onboarding, consent, re-check due).

**AWS**
- [ ] AWS account billing entity for India (AWS India): add GSTIN and PAN so invoices carry GST.
- [ ] Bedrock first-use form (E0b checklist).
- [ ] **SES** production access (exit the sandbox), domain identity with DKIM, SPF and DMARC.

**Verification providers**
- [ ] Sign the contract and DPA with the chosen provider(s) (Q3), plus their merchant KYC of Orsyn.
- [ ] Get sandbox keys first. Put production keys into Admin → Providers only.

**Privacy**
- [ ] Privacy notice and KYC purpose notices (en, hi) reviewed by counsel.
- [ ] Grievance officer named and published.
- [ ] Processor list.
- [ ] Breach runbook.

**Domain and email**
- [ ] Company domain on Google Workspace with enforced 2-step verification (E0b).
- [ ] If SMS is ever used: DLT entity and sender registration.

---

## Appendix B: Provider comparison (capabilities from public pages read on 2026-10-05; **all prices to quote**)

| | Cashfree Secure ID | Surepass | Perfios (incl. Karza) | Signzy | IDfy | Direct government |
| --- | --- | --- | --- | --- | --- | --- |
| GSTIN details | **Yes** (docs: legal and trade name, status, address, registration date, taxpayer type, constitution) | Yes (catalogue) | Yes ("GSTIN, PAN, TAN, Udyam" one-click onboarding) | KYB (not itemised on the home page) | KYB / due diligence (not itemised) | GST public search has a captcha; API only via a GSP licence |
| GST filing status | Not seen in the docs page read | to confirm | likely (GST data products), to confirm | to confirm | to confirm | via GSP |
| PAN | **Yes** | Yes | Yes | Yes | Yes | Protean (NSDL) needs entity registration |
| Udyam | Not seen | **Yes** (Udyam API listed) | **Yes** | to confirm | to confirm | portal with OTP/captcha |
| IEC | Not seen | to confirm | to confirm | to confirm | to confirm | DGFT public lookup (captcha) |
| CIN/LLPIN, directors | Not seen | Yes (MCA "business" APIs) | **Yes** (MCA-profiled entities) | Yes (UBO checks) | to confirm | MCA portal (captcha); MCA data products are paid |
| Bank penny drop + name match | **Yes**, plus **reverse penny drop**, IFSC, name match | Yes | to confirm | Yes | to confirm | — |
| DigiLocker | **Yes** (+ Aadhaar masking) | Yes (API + Web SDK) | to confirm | to confirm | to confirm | DigiLocker partner onboarding is lengthy |
| AML / sanctions | Not seen | Yes (AML) | Yes (AML, PEP, UBO) | Yes (AML screening) | Yes (compliance monitoring) | official lists, free |
| Public docs / sandbox | **Public docs index**; keys, IP allow-listing | Request a key / sales | Sales | Sales | Sales | — |
| Fit for Orsyn | Strongest on the bank path (gates payouts) and has a public API surface | Broadest catalogue; a good secondary or single-provider candidate | Deepest KYB data; enterprise-oriented | Broad; enterprise | Broad; enterprise | Not viable as an API in Phase 1 |

**Recommendation:** Cashfree Secure ID as primary for GSTIN, PAN, bank and name match. A secondary (Surepass or Perfios, decided by quote) for GST filing, Udyam, IEC and CIN/LLPIN, unless Cashfree's quote covers them. In-house sanctions screening. Everything sits behind `VerificationProvider`, so switching is an adapter PR plus an eval-free contract test.

---

## Appendix C: How KYC feeds Razorpay Route (KYC-4, M2)

The required fields of Razorpay's create linked account API (`POST /v2/accounts`, read on 2026-10-05) are listed below with where each comes from. The stakeholder and product-configuration steps (`/v2/accounts/{id}/stakeholders`, `/v2/accounts/{id}/products` with `product_name: route`, then settlements `{account_number, ifsc_code, beneficiary_name}` and `tnc_accepted`) are **from memory, and backend re-checks them against Razorpay's docs** in the M2 payments story.

| Razorpay field | From | Trace |
| --- | --- | --- |
| `legal_business_name` | `org_kyc_profile.legal_name` | `legal_name_check_id` (GSTIN) |
| `business_type` | `org_kyc_profile.constitution` mapped in code (Proprietorship → `proprietorship`, Partnership → `partnership`, Private Limited Company → `private_limited`, Public Limited Company → `public_limited`, LLP → `llp`, Trust, Society, HUF …) | GSTIN check |
| `legal_info.pan` | `org_registrations(kind=pan)` decrypted at send time | PAN check |
| `legal_info.gst` | `org_registrations(kind=gstin, is_primary)` | GSTIN check |
| `profile.addresses.registered` | `org_kyc_profile.registered_address` | GSTIN check |
| `profile.category` / `subcategory` | mapped in code from the supplier's profile category (manufacturing) | supplier profile |
| `contact_name`, `email`, `phone` | the confirmed signatory person (contact data, sent only to Razorpay under the `payouts_share_with_razorpay` consent) | `org_signatories.check_id` |
| Stakeholder name (and PAN where Razorpay asks for it) | `org_signatories` | signatory check |
| Settlements `account_number`, `ifsc_code`, `beneficiary_name` | `bank_accounts` (verified) decrypted at send time; `holder_name_at_bank` | bank check |

The supplier only sees one new screen in M2: "Allow Orsyn to share your verified details with Razorpay to receive payouts", which records consent `payouts_share_with_razorpay`. If Razorpay returns `needs_clarification`, the M2 story maps its requested fields back to the KYC step that supplies them. The supplier is never asked to type anything they have already verified.
