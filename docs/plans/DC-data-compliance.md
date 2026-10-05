# DC — Data compliance baseline and controls

Status: draft, waiting for founder OK and counsel review. Author: architect. Date: 2026-10-05. Story key **DC is provisional** (Q1).

Inputs read: `CLAUDE.md`, `.claude/agents/*`, `.github/pull_request_template.md`, `.claude/settings.json`, `.gitignore`, `.github/workflows/ci.yml`, `services/api/app/{main,settings}.py`, `services/api/app/ai/gateway.py`, `evals/runner.py`, `docs/{build-plan,architecture}.md`, and every plan in `docs/plans/`: E0, E0b, E0d, AST. **`KYC-verification.md` did not exist when this plan was written** (checked 2026-10-05); §C.5 lists what it must meet, and the KYC plan should be audited against this plan once it lands.

Founder's ask, verbatim: "Make sure the architecture is data compliant."

**This plan is not legal advice.** Part A turns laws into engineering requirements for counsel to confirm. Every item cites the primary text that was actually opened, with the date checked. Items whose primary text could not be opened are marked **unverified — counsel to confirm**.

---

## 1. Goal

Make every Orsyn store, log, model call and vendor meet one written compliance baseline (India first, EU/UK where buyers are there), with controls that are tested in CI, so that each story inherits them instead of re-deciding them.

> Done when (**proposed**; `docs/build-plan.md` has no DC entry, the founder confirms, Q1):
> (a) every database column carries a data class, and every store and processor appears in `docs/data-map.md` with its region; CI fails otherwise;
> (b) PAN, bank account numbers and Aadhaar references exist only in `pii_vault`, encrypted under a KMS key, and never appear in logs, events, prompts or API responses except through an audited owner reveal;
> (c) a signed-in person can read the privacy notice (English and Hindi), give and withdraw each optional consent, and raise access, correction, erasure, grievance and nominee requests; each request shows a due date and an SLA timer in the ops console;
> (d) an approved erasure deletes or anonymises the person's data in every store per the retention schedule, keeps legally required records restricted, and is re-applied after a backup restore;
> (e) prod logs are kept ≥ 400 days in ap-south-1; RDS, S3, backups and log groups are encrypted with Orsyn KMS keys; clocks use Amazon Time Sync;
> (f) the ops console holds an incident register with CERT-In (6 h) and DPDP Board (72 h) timers, and alerts before each deadline;
> (g) PostHog loads only after the person opts in to analytics;
> (h) no sensitive (C3) data reaches a model route that processes outside India.

### 1.1 Applicability dates (why build now)

| Regime | In force for Orsyn | Source (checked 2026-10-05) |
| --- | --- | --- |
| CERT-In Directions | **Now** (effective 60 days after 28 Apr 2022) | Directions No. 20(3)/2022-CERT-In, last para; FAQ Q44 |
| DPDP Rules: rules 1, 2, 17–21 | Now (13 Nov 2025) | DPDP Rules 2025, G.S.R. 846(E), rule 1(2) |
| DPDP Rules: rule 4 (Consent Managers) | 13 Nov 2026 | rule 1(3) |
| **DPDP Rules: rules 3, 5–16, 22, 23** (notice, safeguards, breach, erasure, children, rights, transfers) | **13 May 2027** (18 months after 13 Nov 2025) | rule 1(4) |
| DPDP Act ss.3–17 and s.44(2) (omits IT Act s.43A) | 13 May 2027 per commencement notification **G.S.R. 843(E)** | Notification text quoted at dpdpa.com; the official MeitY/e-Gazette page returned 403 — **unverified, counsel to confirm** |
| IT Act s.43A + SPDI Rules 2011 | Until s.44(2) commences | **unverified — counsel to confirm** (SPDI text not opened) |
| EU GDPR | From the first EU buyer (Art. 3(2)(a)) | Art. 3(2), via gdpr-info.eu |

Orsyn launches before May 2027. Consent records, notices, the vault and log retention are cheap to build now and expensive to retrofit (consent cannot be collected retroactively for data already held; RDS encryption cannot be switched on after creation). So the baseline applies to every story from today.

### 1.2 Deliberately not building

- A Consent Manager integration (rule 4). Consent is given directly to Orsyn.
- Third Schedule 3-year inactivity erasure and the 48-hour pre-erasure notice (rule 8(1)–(2)). They bind e-commerce entities with ≥ 2 crore registered users in India; Orsyn is far below. Revisit at 10 lakh users.
- Significant Data Fiduciary duties (DPO in India, DPIA, audit; Act s.10(2), rule 13). Only on notification by the Central Government.
- A GDPR EU representative (Art. 27) until the first EU buyer signs (Q-C6).
- Any India-only replacement for Sonnet/Opus (§A.7). Cost and quality are not justified while C3 data is kept off Global routes.
- A separate privacy service. Everything lives in the api under `app/privacy/`.
- Card data of any kind. Orsyn never sees card numbers (§A.5).
- Storing Aadhaar numbers, ever (§A.3).

### 1.3 Part A — Compliance baseline

Every row is an engineering requirement. "Source" names the section and the date it was opened.

#### A.1 India: DPDP Act 2023 and DPDP Rules 2025

Sources opened 2026-10-05: DPDP Act 2023 (Gazette, Act 22 of 2023; copy at dpdpa.com/DPDPA_2023_official.pdf) and DPDP Rules 2025 (Gazette G.S.R. 846(E), 13 Nov 2025; copy at dpdpa.com/DPDP_Rules_2025_English_only.pdf). The MeitY site returned 403; counsel should confirm against the e-Gazette.

| # | Obligation | Source | Engineering requirement |
| --- | --- | --- | --- |
| D1 | Orsyn is a **Data Fiduciary**: it decides the purpose and means of processing users' personal data | Act s.2(i); s.3(a) | Name Orsyn as fiduciary in the notice. Vendors are Data Processors under a contract (D12) |
| D2 | Lawful grounds: **consent** or **certain legitimate uses** | s.4(1); s.7 | Each processing purpose in `app/privacy/purposes.py` has a basis: `consent`, `legit_use_7a` (data the person gave for that purpose and did not object to), `legal_obligation`, `employment_7i` (staff). Counsel confirms each mapping (Q-C1) |
| D3 | **Notice**: itemised personal data, specified purposes, goods/services enabled, how to withdraw, exercise rights and complain to the Board; standalone and plain | s.5(1); rule 3(a)–(c) | `privacy_notices` table with versioned, itemised purpose list. Notice shown before consent; link to withdraw, rights and Board complaint |
| D4 | Notice and consent request available **in English or any Eighth Schedule language** | s.5(3); s.6(3) | English + Hindi at launch; more with demand (Q-C2) |
| D5 | Consent: free, specific, informed, unconditional, unambiguous, clear affirmative action, limited to necessary data | s.6(1) | No pre-ticked boxes; one checkbox per optional purpose; signup never bundles optional purposes |
| D6 | **Withdrawal** as easy as giving; processing (and processors) stop within reasonable time | s.6(4), 6(6) | Settings → Privacy toggles; withdrawal writes a row and stops the processor (e.g. PostHog `opt_out` + server stops sending) |
| D7 | Fiduciary must **prove notice and consent** | s.6(10) | `consent_records` append-only: person, notice version, purpose, granted/withdrawn, method, time |
| D8 | **Reasonable security safeguards**: encryption/masking/tokens; access control; access logs and monitoring; backups; **retain logs and personal data 1 year** for detection; processor contract clauses | s.8(5); rule 6(1)(a)–(g) | §B3–B6, B11. Log retention ≥ 365 days (we choose 400) |
| D9 | **Breach**: intimate each affected person **without delay**, and the Board **without delay**, then a detailed report **within 72 hours** | s.8(6); rule 7(1), 7(2)(a)–(b) | Incident register with timers (§B10). Person notice via account + registered email |
| D10 | **Erase** when consent withdrawn or purpose no longer served, unless law requires retention; cause processors to erase | s.8(7)(a)–(b) | Retention registry + purge jobs + processor deletion calls (§B9) |
| D11 | **Keep personal data, traffic data and processing logs for at least 1 year** from processing (Seventh Schedule purposes), even after account deletion; processors too | rule 8(3) and Illustrations, Cases 1–2 | Erasure of *content* may still need a 1-year hold of the processing record. Conflicts with AST's 90-day purge (§C.4). Counsel decides scope (Q-C3) |
| D12 | Processors only **under a valid contract**; fiduciary stays responsible | s.8(1)–(2); rule 6(1)(f) | DPA checklist (§B12) before first use of any processor |
| D13 | Publish **contact for privacy questions**; mention it in every rights response | s.8(9); rule 9 | `privacy@<domain>` and a named person in notice and in every DSR reply |
| D14 | **Grievance redressal** mechanism; respond within **≤ 90 days** | s.8(10), s.13; rule 14(3) | DSR workflow with SLA (§B8). We target 30 days to also meet GDPR |
| D15 | **Rights**: access (summary, recipients), correction/completion/updating, erasure, grievance, **nominee** | ss.11–14; rule 14(1)–(4) | `privacy_requests` kinds `access`, `correction`, `erasure`, `grievance`, `nominate`; `nominees` table |
| D16 | **Children** (< 18): verifiable parental consent; no tracking or targeted ads | s.2(f), s.9(1)–(3); rule 10 | Orsyn is B2B: **block under-18**. Signup asks for an 18+ attestation (permitted processing: Fourth Schedule Part B item 6). No parental-consent flow is built (Q-C4) |
| D17 | **Cross-border**: allowed except to countries the Government notifies; sector laws with stricter rules still apply | s.16(1)–(2); rule 15 | No restricting notification was found in the sources opened; **counsel to confirm** (Q-C5). Disclose every non-India processor (§A.7) |
| D18 | **SDF** triggers: volume and sensitivity, risk to principals, sovereignty, State security, public order | s.10(1); rule 13 | Not expected. Watch item for the founder; if notified, DPO in India + annual DPIA/audit |
| D19 | Penalties up to ₹250 crore (safeguards), ₹200 crore (breach notice, children) | Schedule, items 1–3 | Prioritises §B3–B6, B10 |

#### A.2 CERT-In Directions (28 April 2022)

Sources opened 2026-10-05: Directions No. 20(3)/2022-CERT-In (cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf) and FAQs May 2022.

| # | Obligation | Source | Requirement and AWS mapping |
| --- | --- | --- | --- |
| C1 | Report Annexure I incidents (incl. data breach, data leak, unauthorised access, attacks on cloud and AI/ML systems) **within 6 hours of noticing** | Direction (ii); Annexure I items iii, xi, xii, xviii, xx; FAQ Q24, Q30 (partial info allowed, rest later) | Runbook step 1 is the CERT-In report (§B10). Clock starts at "noticed" |
| C2 | Obligation is not transferable; the entity that notices reports, even when the data sits with a vendor | FAQ Q13, Q31 | Our runbook reports even for a vendor incident |
| C3 | Designate a **Point of Contact** for CERT-In | Direction (iii); FAQ Q29 | Founder registers a PoC (Annexure II) before prod launch (Q-F3) |
| C4 | **Enable logs of all ICT systems; keep 180 days rolling, within Indian jurisdiction** | Direction (iv) | All log groups and log buckets in **ap-south-1**. FAQ Q35 allows copies abroad if logs can still be produced; we keep them in India only |
| C5 | Which logs: firewall, web/DB/proxy, application, VPN, SSH; success and failure | FAQ Q37 | CloudWatch app logs, ALB access logs, CloudTrail, RDS logs, VPC flow logs (REJECT). Admin auth successes and failures are in `events` and logs |
| C6 | **Clock sync** to NIC/NPL NTP or a source that does not deviate from them; cloud-native time service allowed | Direction (i); FAQ Q40–Q42 | Fargate uses Amazon Time Sync (native, FAQ Q42). Logs are UTC with an explicit offset (FAQ Q40: record the time zone) |
| C7 | Logs of financial transactions for Indian users in Indian jurisdiction | FAQ Q36 | Payment references and their logs stay in ap-south-1 (§A.5) |

The DPDP 1-year log rule (D8, D11) is longer than CERT-In's 180 days, so **400 days** in prod meets both.

#### A.3 Aadhaar, IT Act s.43A and SPDI Rules

| # | Requirement | Status |
| --- | --- | --- |
| AA1 | Only entities permitted under the Aadhaar Act may perform Aadhaar authentication or store Aadhaar numbers; storage requires an Aadhaar Data Vault; display must be masked | **unverified — counsel to confirm** (UIDAI pages returned 404; the Act PDF could not be read) |
| AA2 | Engineering stance, safe under any reading: **Orsyn never collects, stores, logs or sends to a model a full Aadhaar number.** If KYC needs Aadhaar, the KYC provider does it (offline XML / DigiLocker / provider-hosted flow) and returns only a provider reference id, a verified flag and at most the last 4 digits | Design rule |
| AA3 | Upload filter: images/PDFs that look like Aadhaar cards are refused in general uploads; the redactor masks 12-digit Aadhaar-shaped numbers in text | Design rule |
| SP1 | Until s.44(2) commences, IT Act s.43A and the SPDI Rules 2011 apply: a privacy policy, written consent for sensitive data (passwords, financial information such as bank account details, biometrics), a grievance officer | **unverified — counsel to confirm** (SPDI text not opened). The DPDP-grade controls here are a superset in practice |

#### A.4 Record-keeping laws (and the conflict with erasure)

| # | Record | Retention (commonly cited) | Status |
| --- | --- | --- | --- |
| R1 | GST books, invoices, e-way bills | 72 months from the due date of the annual return for the year (CGST Act s.36) | **unverified — counsel to confirm** (CBIC page 404) |
| R2 | Books of account and vouchers | 8 financial years immediately preceding (Companies Act 2013 s.128(5)) | **unverified — counsel to confirm** |
| R3 | Income-tax books | per the Income-tax Act in force (the 1961 Act was replaced by the Income-tax Act, 2025 from 1 Apr 2026, as understood) | **unverified — counsel to confirm** |
| R4 | DPDP itself permits retention where "necessary for compliance with any law" | Act s.8(7), s.12(3) — verified | Basis for the **retain-for-legal-obligation** rule below |

**Rule (design):** POs, PO lines, invoices, GRNs, payment references and their document lines are retained for **8 full financial years after the FY of the transaction** (the longest of R1–R3 until counsel says otherwise). An erasure request does not delete them. It **restricts** them: personal fields on those rows are kept, flagged `restricted`, hidden from every non-legal read path, and purged when the retention ends.

#### A.5 RBI payment data storage

Source opened 2026-10-05: RBI/2017-18/153, 6 April 2018, "Storage of Payment System Data", issued under PSS Act 2007 ss.10(2), 18.

- It binds **system providers / payment system operators** (and banks): "the entire data relating to payment systems operated by them are stored in a system only in India". A gateway such as Razorpay carries this duty, not Orsyn.
- **Orsyn must:** never collect or store card numbers, CVV, UPI PINs or netbanking credentials (use the gateway's hosted checkout); store only gateway ids (order id, payment id, refund id), amount (`Decimal` + currency), status, time and UTR where given; keep these and their logs in ap-south-1 (CERT-In FAQ Q36).
- **Orsyn need not:** localise anything beyond that or be audited under the circular.
- Supplier payout bank accounts are C3 and live in `pii_vault`.

#### A.6 EU GDPR and UK

Sources opened 2026-10-05: GDPR Arts. 3(2), 27(1)–(2), 33(1), 46(1)–(2) (text via gdpr-info.eu; EUR-Lex returned no text — counsel to confirm against the OJ); European Commission adequacy page.

| # | Point | Requirement |
| --- | --- | --- |
| G1 | GDPR applies to a non-EU controller **offering goods or services to data subjects in the Union** (Art. 3(2)(a)) | M4 (first export order) brings EU buyers. Their staff are data subjects. Treat Orsyn as in scope from the first EU buyer |
| G2 | **EU representative** required (Art. 27(1)) unless processing is occasional, not large-scale special-category, and low-risk (Art. 27(2)(a)) | Counsel decides whether the exemption fits (Q-C6). Budget a representative service if not |
| G3 | Breach to the supervisory authority within **72 hours where feasible** (Art. 33(1)) | Same 72 h timer as DPDP (§B10) |
| G4 | **India has no EU adequacy decision** (Commission list checked 2026-10-05) | Transfers *from* an EU controller to Orsyn need Art. 46 safeguards, e.g. SCCs (Art. 46(2)(c)). When an EU buyer's staff sign up directly with Orsyn, whether that is a "transfer" is a counsel question (Q-C7). Offer SCCs in the buyer contract either way |
| G5 | Data subject response time (1 month, Art. 12(3)) | **unverified** (Art. 12 not opened). Our 30-day internal SLA is set to meet it |
| U1 | UK GDPR mirrors the EU rules for UK buyers; India has no UK adequacy regulation | **unverified — counsel to confirm** |

#### A.7 Data residency decisions already open

| Flow | What leaves India | Permitted under DPDP s.16? | What to disclose | India-only alternative and cost | Decision proposed |
| --- | --- | --- | --- | --- | --- |
| **Bedrock Global** for Sonnet/Opus (E0b §5.2) | Prompts: drawings, documents, RFQ text. AWS states data stays on the AWS network, encrypted between Regions; CloudTrail logs in the source Region (Bedrock user guide, "cross-Region inference", checked 2026-10-05). Model providers have no access to prompts (Bedrock "Data protection") | Yes, unless a country is notified (none found; Q-C5). Not allowed for C3 by our own rule | "AI processing by Amazon Web Services may take place in AWS Regions outside India" | No India-only Sonnet/Opus route exists (E0b check). Options: Haiku-role on `in.` only (likely fails the 90% drawing eval), or a self-hosted open model on a Mumbai GPU (≈ US$750+/mo for one g5-class instance, plus eval work) | **Accept Global for C1/C2 with minimisation; C3 never sent** (gateway guard, §B14). Global is also ~10% cheaper per AWS |
| **PostHog EU** (E0d §1.6) | Pseudonymous events (internal uuids), masked replays | Yes (s.16), Frankfurt per PostHog docs. Analytics is not necessary for the service, so it needs **consent** (D5) | "Product analytics by PostHog, Frankfurt (EU), only if you opt in" | Self-hosted PostHog in Mumbai: not cost-effective at our size (needs ClickHouse; ≈ US$150+/mo); or drop replays | **EU Cloud, opt-in only, replay off until counsel agrees** |
| **SES** (E0d Q6) | Email content to recipients | n/a if hosted in India | Name SES as processor | SES API and SMTP endpoints exist in **ap-south-1** (AWS endpoints page, checked 2026-10-05) | **Use SES in ap-south-1** |
| **WhatsApp Cloud API** (Meta) | Message content, phone numbers | Yes (s.16); Meta is a processor for our business messages | "Messages on WhatsApp are processed by Meta" | None: every BSP relays through Meta's cloud | Accept and disclose (Q-F5 confirms BSP) |
| **KYC provider** (KYC plan pending) | PAN, bank, Aadhaar flows | Must be India-hosted by our rule (C3 stays in India) | Name provider and purpose | Choose an India-hosted provider; require it in the DPA | **Blocker for the KYC plan**, not for DC |
| **Sarvam** | Indian-language text and voice | n/a if India-hosted | Name Sarvam | Sarvam is an Indian company; hosting location **unverified** | Confirm in DPA (Q-F6) |
| **Direct Anthropic API** (E0b Q7, deferred) | Prompts to Anthropic (US) | Yes (s.16) | Name Anthropic | n/a | If ever enabled: DPA, zero-retention terms, same C3 guard |

### 1.4 Part B — Architecture controls (index)

| # | Control | Where it is specified | Built by |
| --- | --- | --- | --- |
| B1 | Data classes C0–C3 on every column | §2.1 | backend |
| B2 | `docs/data-map.md` of every store and processor with region | Appendix D.2 | infra (+ backend rows) |
| B3 | Encryption at rest (KMS CMKs) and in transit | §2.7 | infra |
| B4 | Field-level encryption for PAN, bank account, Aadhaar refs (`pii_vault`) | §2.4 | backend |
| B5 | Log redaction helper; ban on bodies | §2.8 | backend |
| B6 | Backups: retention and erasure behaviour | §2.7, §2.6 | infra, backend |
| B7 | Notice and consent records | §2.2 | backend, frontend |
| B8 | DSR workflow with SLA timers in the ops console | §2.3, §3, §7 | backend, frontend |
| B9 | Retention schedule registry and purge jobs | §2.6 | backend, infra |
| B10 | Breach runbook and incident register | §2.5, §4, §7 | backend, infra |
| B11 | Staff access control and audit | §3.3 | backend, infra |
| B12 | Processor DPA checklist | §6.2 | founder, counsel |
| B13 | Privacy notice and analytics consent for PostHog | §7 | frontend |
| B14 | Model-prompt minimisation and residency guard | §5 | ai-engineer |
| B15 | Fixtures rule enforced in CI | §8.3 | qa-evals |
| B16 | Dev and CI never hold real personal data | §2.9 | infra |

---

## 2. Ontology impact

All new tables have `id` (uuid), `org_id`, `created_at` (timestamptz UTC) and `created_by` (`person:<uuid>`, `agent:<name>` or `system:<component>`), per E0b. Platform-owned tables use the platform org. No documents or PO lines are created; the document-line → PO-line link is untouched, and the retain-for-legal-obligation rule (§A.4) protects those rows.

### 2.1 Data classes (B1)

| Class | Meaning | Examples | Allowed in logs / events / prompts |
| --- | --- | --- | --- |
| **C0 public** | Published by design | showcase page text, HSN codes, rules | yes |
| **C1 business-confidential** | Commercial data of an org | prices, drawings, quotes, POs, GSTIN of a company | logs: ids only; events: ids only; prompts: yes, minimised |
| **C2 personal** | About an identifiable individual | name, work email, phone, IP, user id, proprietor's GSTIN, WhatsApp number, chat text | logs/events: ids only (masked if unavoidable); prompts: only what the task needs, contacts masked (CLAUDE.md rule 5) |
| **C3 sensitive** | Identity and money identifiers | PAN, bank account + IFSC, Aadhaar reference/last 4, KYC document images, signatures | **never** in logs, events, exports or prompts on Global routes; only in `pii_vault` and private S3 `kyc/` prefix |

**Mechanism:** every SQLAlchemy column declares `info={"data_class": "C0|C1|C2|C3"}`. A test (§8) walks `Base.metadata` and fails on an untagged column, and on any C3 column outside `pii_vault`. The same test checks that every table name appears in `docs/data-map.md`.

### 2.2 `privacy_notices` and `consent_records` (B7)

`privacy_notices` (platform org):
| Column | Type | Notes |
| --- | --- | --- |
| `version` | int | unique with `locale` |
| `locale` | text check in (`en`,`hi`) | |
| `purposes` | jsonb | `[{purpose, basis, data_items[], required: bool, processors[]}]`; itemised per rule 3(b) |
| `body_md_sha256` | char(64) | the notice text lives in the repo (`apps/web/content/privacy/<locale>/v<n>.md`); the hash proves which text was shown |
| `published_at` | timestamptz | |

`consent_records` (append-only; trigger blocks UPDATE/DELETE):
| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | the person's org (platform org before org creation) |
| `person_id` | uuid | |
| `purpose` | text | from `app/privacy/purposes.py` enum: `age_18_plus`, `account_and_service`, `whatsapp_updates`, `product_analytics`, `session_replay`, `marketing_email` (Q-C1 confirms the list and bases) |
| `granted` | bool | false = withdrawal |
| `notice_version`, `notice_locale` | int, text | FK to `privacy_notices` |
| `method` | text check in (`signup_form`, `settings`, `banner`, `whatsapp_reply`, `staff_on_request`) | |
| `request_id` | text | links to logs (IP stays in logs, not here) |

Current state = latest row per (`person_id`, `purpose`), from a view `consent_current`.

### 2.3 `privacy_requests` and `nominees` (B8)

`privacy_requests`:
| Column | Type | Notes |
| --- | --- | --- |
| `org_id`, `person_id` | uuid | subject |
| `kind` | text check in (`access`,`correction`,`erasure`,`grievance`,`nominate`,`withdraw_all`) | |
| `source` | text check in (`app`,`email`,`whatsapp`,`nominee`) | email/WhatsApp requests are logged by staff |
| `status` | text check in (`received`,`identity_check`,`in_progress`,`fulfilled`,`rejected`,`closed`) | |
| `received_at`, `due_at` | timestamptz | `due_at = received_at + 30 days` (internal SLA; legal ceiling 90 days for DPDP grievances, rule 14(3)) |
| `details` | text null | C2, max 2000 chars, redacted for C3 patterns on write |
| `outcome_code`, `outcome_note` | text | e.g. `erased`, `restricted_legal_hold`, `corrected`, `rejected_identity` |
| `export_s3_key` | text null | access exports; object expires in 7 days |
| `assigned_to` | text null | staff id |
| `decided_by`, `decided_at` | | |

`nominees`: `org_id`, `person_id`, `nominee_name` (C2), `nominee_email` (C2), `relationship`, `active`. One active nominee per person.

### 2.4 `pii_vault` (B4)

| Column | Type | Notes |
| --- | --- | --- |
| `org_id` | uuid | |
| `subject_type`, `subject_id` | text, uuid | `person` or `org` |
| `kind` | text check in (`pan`,`bank_account`,`ifsc`,`aadhaar_ref`,`kyc_provider_ref`) | `aadhaar_ref` = provider reference + last 4, **never** the number |
| `ciphertext` | bytea | AES-256-GCM with a per-row data key from KMS `GenerateDataKey` on `alias/orsyn-<env>-pii`; encryption context `{org_id, kind, id}` |
| `encrypted_data_key` | bytea | |
| `last4` | char(4) | for display |
| `fingerprint` | char(64) | HMAC-SHA256 with a key in Secrets Manager, for duplicate detection without decrypting |
| `purge_after` | timestamptz null | set by retention |
| `restricted` | bool | legal-obligation retention after an erasure request |

- Domain tables store only the vault row id. Only `app/privacy/vault.py` can decrypt; every decrypt writes `pii.revealed` with purpose.
- Uses the `cryptography` package (new dependency, justified) and boto3 KMS. No new service.

### 2.5 `incidents` (B10, platform org, no personal data)

| Column | Type | Notes |
| --- | --- | --- |
| `title` | text | no personal data |
| `severity` | text check in (`sev1`,`sev2`,`sev3`) | |
| `categories` | text[] | CERT-In Annexure I item numbers |
| `personal_data_involved` | text check in (`unknown`,`no`,`yes`) | |
| `eu_data_involved` | bool | |
| `noticed_at` | timestamptz | starts every clock |
| `cert_in_due_at` | timestamptz | `noticed_at + 6 h` |
| `board_due_at` | timestamptz | `noticed_at + 72 h` (detailed report; initial intimation "without delay") |
| `cert_in_reported_at`, `board_initial_at`, `board_detailed_at`, `principals_notified_at`, `gdpr_sa_notified_at` | timestamptz null | |
| `affected_count` | int null | |
| `status` | text check in (`open`,`contained`,`closed`) | |
| `lessons` | text null | |

### 2.6 Retention, legal holds and erasure (B6, B9)

**Retention registry** `app/privacy/retention.py` (code, changed by PR, like `routing.py`). Each row: `category`, `store`, `class`, `retain`, `trigger`, `basis`, `action` (`delete`/`anonymise`/`restrict`), `source`, `checked_on`. A test fails if any `checked_on` is older than 180 days.

| Category | Store | Retain | Action at end | Basis |
| --- | --- | --- | --- | --- |
| App, ALB, RDS, VPC-flow and CloudTrail logs | CloudWatch / S3 ap-south-1 | **400 days** prod, 180 days dev | expire | CERT-In (iv); DPDP rule 6(1)(e), 8(3) |
| Account profile (name, email, phone) | RDS | while active; then **1 year** after closure or erasure | anonymise | rule 8(3) (Q-C3) |
| Consent records, notices | RDS | life of account + 7 years | delete | s.6(10) burden of proof; mirrors Consent Manager 7 years (First Schedule Part B item 4(c)); Q-C8 |
| Privacy requests | RDS | 7 years after closure | delete | proof of compliance; Q-C8 |
| POs, PO lines, invoices, GRN, payment refs, their document lines | RDS, S3 | **8 FY after the FY of transaction** | delete | §A.4 (unverified) |
| RFQs, quotes, drawings not leading to a PO | RDS, S3 | 3 years after last activity | delete (drawings) / anonymise (rows) | product need; Q-F7 |
| KYC images | S3 `kyc/` | 30 days after the verification decision | delete | minimisation; KYC plan confirms |
| C3 vault rows | RDS | while the relationship lasts; restricted rows to legal end | delete | §A.4 |
| Assistant conversations | RDS | 90 days (AST) — **pending Q-C3** | delete | AST §2.1 |
| `error_occurrences` | RDS | 30 days (E0d) | delete | derived telemetry; source logs keep 400 days |
| RDS automated backups | AWS | 7 days | AWS expiry | §2.7 |
| S3 noncurrent object versions | S3 | 30 days | lifecycle expiry | erasure completes in 30 days |
| PostHog events and persons | PostHog EU | per PostHog plan; person deleted on erasure | API delete | D10 |

**`legal_holds`** (platform org): `subject_type`, `subject_id`, `reason_code` (`litigation`, `regulator_request`, `tax_audit`), `note`, `placed_by`, `released_at`. Purges and erasures skip held subjects and record `skipped_hold`.

**`erasure_tombstones`**: `subject_type`, `subject_id`, `erased_at`, `request_id`. No personal data. After any RDS restore, the runbook runs `erasure.reapply` over every tombstone newer than the restore point before the app takes traffic. Backups age out after 7 days, so a restore never resurrects erased data for longer than that window.

**Erasure executor** (`app/privacy/erasure.py`): driven by a per-table **erasure map** (`app/privacy/erasure_map.py`) generated from the data classes: for each table with C2/C3 columns, the subject key and action. A test fails if a table with C2/C3 columns is missing from the map. Each run is a **dry run first** (counts per table, rows restricted for legal reasons), then an owner confirms (§3.2).

### 2.7 Encryption and backups (B3, B6) — infra

- **Two customer-managed KMS keys per environment**: `alias/orsyn-<env>-data` (RDS storage, RDS snapshots, S3 SSE-KMS with bucket keys, CloudWatch log groups, SQS) and `alias/orsyn-<env>-pii` (vault only; key policy: api task role `Encrypt/Decrypt/GenerateDataKey` with `kms:EncryptionContext:kind` condition; no human principal except a break-glass role). Annual automatic rotation on.
- **RDS**: `storage_encrypted = true` with the data key **at creation** (cannot be enabled later without snapshot-copy-restore). Parameter `rds.force_ssl = 1`. Automated backups 7 days; deletion protection on; final snapshot on delete; manual snapshots only before migrations, tagged and expired at 30 days.
- **S3**: block public access (account level), bucket policy denies non-TLS and non-KMS puts, versioning on, noncurrent versions expire at 30 days, access logs to the log bucket.
- **In transit**: ALB TLS policy TLS 1.2+ only (TLS 1.3 preferred), HSTS at the web layer, VPC endpoints for S3, KMS, Secrets Manager, Logs, SQS and Bedrock so service traffic stays on AWS.
- Secrets Manager keeps the default `aws/secretsmanager` key (E0b decision stands).

### 2.8 Logging rules (B5) — backend

- One JSON formatter (`app/observability/logging.py`) with an **allow-list of `extra` keys** (ids, enums, counts, durations, status codes, request id, route template). Unknown keys are dropped, not printed.
- Every string value passes `app/privacy/redact.py`: email, Indian phone (+91 / 10 digits), PAN (`[A-Z]{5}[0-9]{4}[A-Z]`), Aadhaar-shaped 12 digits, IFSC, and 9–18-digit account-number-shaped runs are masked. The same redactor serves AST's `redact.py` and E0d's log filter (one implementation).
- **Banned:** logging request or response bodies, headers (`Authorization`, `Cookie`, `Set-Cookie`), full query strings, Pydantic validation `input` values, exception messages from vendors, and prompt or completion text. The exception handler logs exception type, location and `loc` paths only.
- Timestamps are ISO-8601 UTC with `Z` (CERT-In FAQ Q40). Uvicorn access logs print the route path without the query string.

### 2.9 Dev and CI hold no real personal data (B16)

- Dev uses synthetic seed data only (`services/api/app/devseed/`, fake names on `example.com`, phone numbers from a reserved fake range).
- No prod snapshot, export or log copy is restored into dev, local or CI. Enforced by separate AWS accounts (E0b Q11) and a prod KMS key policy that names no dev principal.
- CI has no AWS credentials (E0 stands) and `pytest-socket` blocks the network (E0b stands).

---

## 3. API

Common rules as E0b/AST: customer routes on `/v1`, admin routes on `/admin/v1` (admin host, ALB OIDC, `staff_admins`, CSRF header, `include_in_schema=False`). Errors `{"error": {"code","message"}}`. Times ISO-8601 UTC; the UI shows IST.

### 3.1 Customer (any signed-in person; data scoped to `person_id` **and** `org_id`; another person's id returns 404)

| Method and path | Request | Response | Errors |
| --- | --- | --- | --- |
| `GET /v1/privacy/notice?locale` | | `{version, locale, purposes[], body_url}` (also public, unauthenticated, for the `/privacy` page) | 404 locale |
| `GET /v1/privacy/consents` | | `[{purpose, granted, required, at, notice_version}]` | |
| `POST /v1/privacy/consents` | `{purpose, granted, notice_version}` | the new current state | 409 `stale_notice` (re-show notice); 422 `required_purpose` (cannot withdraw `account_and_service` without closing the account) |
| `POST /v1/privacy/requests` | `{kind, details?}` | `{id, kind, status, due_at}` | 409 `open_request_exists` (same kind); 429 (5 per day) |
| `GET /v1/privacy/requests` | | own requests | |
| `GET /v1/privacy/requests/{id}/export` | | `{url, expires_at}` 15-minute presigned S3 URL, only when an `access` request is `fulfilled` | 404; 410 `expired` |
| `PUT /v1/privacy/nominee` / `DELETE` | `{name, email, relationship}` | nominee | 422 |

The access export is a JSON + PDF summary per s.11(1): personal data held, processing purposes, and the processors and other fiduciaries it was shared with (from the data map). **Supplier contacts masked before award stay masked in a buyer's export** (rule 5); a person's own data is never masked to themselves.

### 3.2 Admin (ops console)

| Method and path | Who | Request | Response | Errors |
| --- | --- | --- | --- | --- |
| `GET /admin/v1/privacy/requests?status&kind&sla` | viewer, owner | | `[{id, org_name, kind, source, status, received_at, due_at, sla_state ∈ {ok, due_soon, overdue}}]`; subject shown as id + masked email | |
| `GET /admin/v1/privacy/requests/{id}` | viewer, owner | | request + timeline events + erasure dry-run (if any) | 404 |
| `POST /admin/v1/privacy/requests` | owner | `{person_id, kind, source:"email"\|"whatsapp", details}` | request | 404 person |
| `POST …/{id}/identity-verified` | owner | `{method}` | request | 409 |
| `POST …/{id}/erasure/dry-run` | owner | `{}` | `{tables:[{table, rows, action}], restricted:[...], held: bool}` | 409 not erasure |
| `POST …/{id}/erasure/execute` | owner | `{dry_run_id, confirm: "ERASE"}` | `{erased_counts, restricted_counts, tombstone_id}` | 409 dry run older than 10 min or data changed; 409 `legal_hold` |
| `POST …/{id}/fulfil` / `reject` | owner | `{outcome_code, note}` | request | 409 |
| `GET/POST /admin/v1/privacy/legal-holds`, `POST …/{id}/release` | owner (viewer reads) | `{subject_type, subject_id, reason_code, note}` | hold | |
| `GET/POST/PATCH /admin/v1/incidents` | owner (viewer reads) | timestamps per §2.5 | incident with timers | 422 time before `noticed_at` |
| `POST /admin/v1/pii/{vault_id}/reveal` | owner | `{reason_code, note 10–200}` | `{value, expires_in_s: 60}` | 403 viewer; 429 > 5 per staff per day |

Staff never edit customer business data (E0b rule). Corrections are made by the person in Settings; staff only fulfil access and erasure and record grievances.

### 3.3 Staff access control and audit (B11)

- E0b roles stand. DSR execution, legal holds, incidents and vault reveal are **owner-only**, each with a reason and an event.
- **No standing human access to prod data.** A break-glass IAM role (MFA, 1-hour session, `aws:MultiFactorAuthPresent`) is the only path to RDS (IAM auth) and to the PII key; assuming it fires an SNS critical alert and is logged in CloudTrail.
- A quarterly access review (staff list, IAM roles, vendor seats) is recorded as `staff.access_reviewed`.

---

## 4. Events

Same `events` shape as E0b/E0c. **Payloads hold ids, enums, counts and times only; never names, emails, phones, C3 values or request text.**

| Type | Actor | Source | Payload |
| --- | --- | --- | --- |
| `privacy.notice_published` | person (staff) | admin_cli | `{version, locale, sha256}` |
| `consent.granted` / `consent.withdrawn` | person | web/pwa/whatsapp | `{purpose, notice_version, method}` |
| `privacy_request.created` / `.identity_verified` / `.fulfilled` / `.rejected` / `.closed` | person or staff | web/admin_ui | `{request_id, kind, outcome_code?}` |
| `privacy_request.sla_due_soon` / `.sla_overdue` | `system:privacy_sla` | job | `{request_id, due_at}` |
| `erasure.dry_run` / `erasure.executed` | person (owner) | admin_ui | `{request_id, tables, counts, restricted_counts}` |
| `erasure.reapplied_after_restore` | `system:erasure_reapply` | job | `{tombstones, restore_point}` |
| `retention.purge_run` | `system:retention_purge` | job | `{category, deleted, anonymised, skipped_hold}` |
| `legal_hold.placed` / `.released` | person (owner) | admin_ui | `{hold_id, subject_type, subject_id, reason_code}` |
| `pii.vault_written` / `pii.revealed` | person or `system:<job>` | web/admin_ui | `{vault_id, kind, purpose}` |
| `incident.opened` / `.updated` / `.cert_in_reported` / `.board_notified` / `.principals_notified` / `.closed` | person | admin_ui | `{incident_id, field, at}` |
| `nominee.set` / `.removed` | person | web | `{}` |
| `staff.access_reviewed` | person | admin_cli | `{reviewed_count}` |
| `processor.person_deleted` | `system:erasure` | job | `{processor, ok}` (e.g. PostHog) |

Log lines for alarms: `orsyn.privacy.sla` and `orsyn.incident.deadline` (metric filters, §8.4).

---

## 5. AI agents

**No new agent and no prompt.** One gateway change (B14), owned by ai-engineer:

- `ModelRequest` gains `data_classes: frozenset[Literal["C0","C1","C2","C3"]]`, declared by the calling agent.
- `routing.py` rows gain `residency: Literal["in", "global"]` (`in.` profiles and Sarvam-in-India = `in`; `global.` profiles = `global`).
- The gateway **refuses** (typed `ResidencyViolation`, `model_calls.status = blocked_residency`) any request with `C3` on a `global` route, before any provider call.
- As a second layer, the gateway runs the C3 patterns from `redact.py` over message text for `global` routes; on a hit it blocks the call and logs only the pattern name.
- Prompt minimisation rules stay as in CLAUDE.md and `ai-engineer.md`; agents send ids and the fields the task needs, never contacts before award.
- Bedrock model-invocation logging stays **off** (E0b).

No confidence field or approval point applies: the guard is code, not a model.

---

## 6. Rules

### 6.1 `packages/rules`

None read. Legal retention periods and timers are not export or scheme rules; they live in `app/privacy/retention.py` and `app/privacy/deadlines.py` with `source` and `checked_on`, are mirrored in `docs/data-map.md`, and never appear in a prompt.

### 6.2 Processor DPA checklist (B12) — founder and counsel, before first use

Every processor needs, in writing: (1) processing only on Orsyn's instructions and for listed purposes; (2) security safeguards meeting rule 6(1); (3) breach notice to Orsyn without undue delay, target ≤ 24 h, with CERT-In-ready facts; (4) a sub-processor list and change notice; (5) erasure or return at end, and on request (s.8(7)(b)); (6) log retention ≥ 1 year where it processes for us (rule 8(3) Case 2); (7) processing regions named; (8) no training on our data; (9) GDPR Art. 28 terms and SCCs where EU data is involved; (10) audit or certification evidence (SOC 2 / ISO 27001).

| Processor | Data | Region | DPA status |
| --- | --- | --- | --- |
| AWS (RDS, S3, ECS, SES, Bedrock, CloudWatch…) | C0–C3 | ap-south-1; Bedrock Global for C1/C2 | AWS DPA via service terms — **confirm** |
| PostHog | pseudonymous C2 | EU (Frankfurt) | sign DPA — **todo** |
| Sarvam | C1/C2 text, voice | India? **confirm** | **todo** |
| Meta (WhatsApp Cloud) or BSP | C2 | Meta cloud | **todo** (Q-F5) |
| KYC provider | C3 | must be India | **todo** (KYC plan) |
| Payment gateway (e.g. Razorpay) | payment refs; bank for payouts | India (RBI) | **todo**; may be an independent fiduciary for its own KYC — counsel |
| Google Workspace (staff IdP) | staff C2 | Google | existing terms — **confirm** |
| GitHub | code only; **no personal data allowed** | US | n/a by rule |

---

## 7. Screens

`docs/screens.md` is a stub; frontend builds to `frontend.md` and this section, and the founders add these screens to `screens.md` (Q-F8). Light theme, plain copy, no "AI" wording.

| Screen | Holds | Empty | Loading | Error |
| --- | --- | --- | --- | --- |
| **Public privacy notice** `/privacy` (EN/HI switch) | Notice text v<n>, itemised table of data → purpose → basis → processors and regions, rights, contact, Board complaint link, version and date | n/a | skeleton | "Couldn't load the notice." + Retry |
| **Signup consent step** (inside the login story's signup) | 18+ attestation (required), "Account and service" (required, explained), optional: WhatsApp updates, product analytics, marketing email — unticked; link to full notice | n/a | button "Saving…" | inline: "Please confirm you are 18 or older."; under-18 → "Orsyn is for businesses. You must be 18 or older." and no account is created |
| **Analytics banner** (buyer app and PWA, first visit after login) | "Help us improve Orsyn with analytics?" **Allow** / **Don't allow**, equal weight, link to notice. PostHog is not initialised until Allow | n/a | n/a | n/a |
| **Settings → Privacy** | Consent toggles with dates; "Download my data"; "Correct my details" (links to profile); "Delete my account" (explains what is kept for law and for how long); nominee; my requests with status and due date (IST) | "No requests." | skeleton | per-action inline errors |
| **Admin → Privacy requests** `/admin/privacy` | Queue: kind, org, source, received, due (IST), SLA state (ok / due soon in warn / overdue in bad). Detail: timeline, identity check, erasure dry-run table, Execute (type ERASE), Fulfil / Reject with reason | "No open requests." in ok | skeleton | error + Retry |
| **Admin → Legal holds** | List and place/release with reason | "No holds." | skeleton | error + Retry |
| **Admin → Incidents** `/admin/incidents` | Register; detail shows the **CERT-In 6 h** and **Board 72 h** countdowns, each timestamp field, links to the runbook | "No incidents." | skeleton | error + Retry |

Side panel addition (E0d order): … Health, **Privacy, Incidents**, then E0b's pages.

---

## 8. Tests and evals (qa-evals)

### 8.1 One test per proposed "Done when" clause

| Clause | Test |
| --- | --- |
| (a) data classes + data map | `test_every_column_has_data_class`; `test_c3_columns_only_in_pii_vault`; `test_every_table_in_data_map` (parses `docs/data-map.md`); `test_erasure_map_covers_c2_c3_tables` |
| (b) vault only, audited reveal | `test_vault_ciphertext_not_plaintext` (stub KMS); `test_no_c3_value_in_any_column_log_or_event` (scan all text/jsonb columns, caplog, event payloads after writing a PAN and account); `test_reveal_owner_only_reason_and_event`; `test_api_responses_show_last4_only` |
| (c) notice, consent, DSR | `test_consent_append_only_and_current_view`; `test_withdraw_stops_processing` (PostHog server wrapper no-ops after withdrawal); `test_stale_notice_409`; `test_request_due_at_30_days`; `test_sla_states`; web `privacy-settings.test.tsx`, `notice.test.tsx` (EN/HI) |
| (d) erasure | `test_erasure_dry_run_then_execute`; `test_po_rows_restricted_not_deleted`; `test_legal_hold_blocks_erasure`; `test_reapply_tombstones_after_restore` (restore fixture DB, reapply, assert erased) |
| (e) retention, encryption, time | infra plan/synth assertions: every log group retention ≥ 400 (prod) / 180 (dev) and KMS-encrypted; RDS `storage_encrypted` with the data CMK; S3 policies deny non-TLS; `test_log_timestamps_utc_z` |
| (f) incidents | `test_incident_deadlines_computed`; `test_deadline_alert_log_line_shape`; infra assertion for the alarms in §8.4 |
| (g) PostHog opt-in | web `analytics.test.ts`: no init without `product_analytics` consent even with a key; replay not started without `session_replay`; withdrawal calls `opt_out_capturing` |
| (h) residency guard | `test_c3_blocked_on_global_route_without_provider_call`; `test_c3_pattern_in_text_blocks_global_call`; `test_c3_allowed_on_in_route` |

### 8.2 Negative tests (always)

- **Masking before award:** a buyer's access export, DSR detail and admin request views contain no unawarded supplier phone/email/website (regex scan); erasure dry-run output shows counts, never values.
- **`org_id` isolation:** two orgs, two persons each: consents, requests, exports and nominee are invisible across persons and orgs (404); admin repositories require `PlatformScope`.
- **Approval required:** erasure cannot execute without a fresh dry run and an owner confirmation; no privacy route sends outbound messages except the system's own DSR acknowledgement and breach notices, which go through `approvals` with the owner as approver.
- **Logging:** fuzz test feeds C2/C3 values through request bodies, headers, query strings, validation errors and exceptions; captured logs contain none of them.
- **Under-18:** signup without attestation → 422 and no person row.

### 8.3 Fixtures rule (B15)

`test_fixtures_contain_no_real_pii`: scans `tests/fixtures/**`, `services/api/tests/**`, `evals/**/cases.jsonl` for email domains other than `example.com`/`example.in`, phone numbers outside the reserved fake range, PAN- and Aadhaar-shaped strings not on an allow-list. Runs in CI.

### 8.4 Alarms (infra)

| Alarm | Source | Threshold | Topic |
| --- | --- | --- | --- |
| DSR due soon / overdue | `orsyn.privacy.sla` | due in ≤ 5 days / overdue | info / critical |
| Incident CERT-In deadline | `orsyn.incident.deadline` | `cert_in_reported_at` null at T+4 h | critical |
| Incident Board deadline | same | `board_detailed_at` null at T+60 h | critical |
| Break-glass role assumed | CloudTrail `AssumeRole` on that role | ≥ 1 | critical |
| PII key used by a non-api principal | CloudTrail KMS `Decrypt` | ≥ 1 | critical |

### 8.5 Evals

No agent change. `_smoke` stays at 100%. If an agent later handles C3 (KYC), its eval suite adds "C3 sent to a global route = 0" as a blocking metric.

---

## 9. Cost

**Model calls per user action: 0.** No feature name is needed; the prefix `privacy_` is reserved.

**AWS, monthly** (list prices; infra confirms in PR 1):

| Item | Dev | Prod |
| --- | --- | --- |
| 2 KMS CMKs × US$1 | US$2 | US$2 |
| KMS requests (vault + S3 bucket keys) | < US$0.10 | < US$0.20 |
| CloudWatch Logs extra storage (180 d dev, 400 d prod; assumes ~1 GB/mo dev, ~3 GB/mo prod ingested) | ≈ US$0.20 | ≈ US$1.20 |
| CloudTrail (first management trail free) + S3 storage | < US$0.20 | < US$0.50 |
| ALB access logs + VPC flow logs (REJECT only) to S3 | < US$0.30 | < US$1 |
| S3 noncurrent versions (30 d) | < US$0.10 | < US$0.30 |
| **Total** | **≈ US$3 (₹255)** | **≈ US$5 (₹425)** |

**Total ≈ US$8/month (≈ ₹680 at ₹85/US$).** E0d's 30-day retention estimate rises by the CloudWatch line above.

Not AWS (founder decisions): counsel review; an EU GDPR representative service if Art. 27(2) does not apply (vendor quotes needed, Q-C6); the India-only model alternative (≈ US$750+/mo) is **not** proposed.

---

## 10. PR split

**Prerequisites:** E0 merged; E0c (Alembic, `orgs`, `events`); E0b PRs 1–3 (admin auth, `PlatformScope`, gateway core); the customer login story for the signup step; IaC choice and AWS account for infra PRs.

| # | PR | Builder(s) | ~Lines | Labels |
| --- | --- | --- | --- | --- |
| 1 | **Infra baseline** (must land with or before the first RDS/S3 creation): 2 CMKs, RDS encryption + `force_ssl` + backup settings, S3 policies/versioning/lifecycle, log group retention 400/180 + KMS, CloudTrail, ALB access logs, VPC flow logs, VPC endpoints, break-glass role + alarm | infra | ~380 | needs-founder, security-review |
| 2 | Data classes: column `info` convention, `app/privacy/classes.py`, metadata test; `docs/data-map.md` from Appendix D.2; data-map test | backend, infra (doc), qa-evals | ~300 | |
| 3 | Logging: JSON formatter with allow-list, `app/privacy/redact.py`, exception-handler rule, uvicorn access log; fuzz tests. **Coordinate with E0d PR 2** (one helper) | backend, qa-evals | ~350 | security-review |
| 4 | Gateway residency guard: `data_classes`, `routing.residency`, `ResidencyViolation`, C3 text scan, `blocked_residency` status; tests | ai-engineer, qa-evals | ~250 | security-review |
| 5 | Migration `privacy_notices`, `consent_records` (+ trigger, view), `nominees`; purposes registry; notice/consent/nominee API; tests | backend, qa-evals | ~380 | needs-founder, security-review |
| 6 | Migration `privacy_requests`, `legal_holds`, `erasure_tombstones`; customer DSR API; SLA job + log line; tests | backend, qa-evals | ~390 | needs-founder, security-review |
| 7 | Migration `pii_vault`; `vault.py` (KMS envelope, HMAC fingerprint); reveal endpoint; new dep `cryptography`; tests | backend, qa-evals | ~350 | needs-founder, security-review |
| 8 | Retention registry, purge job, erasure map + executor (dry run, execute, reapply), access export job, PostHog person delete; tests | backend, infra (scheduler rule), qa-evals | ~400 | needs-founder (data deletion), security-review |
| 9 | Migration `incidents`; admin API; deadline job + log lines; tests | backend, qa-evals | ~280 | needs-founder |
| 10 | Web: `/privacy` page EN/HI, signup consent step, analytics banner and PostHog consent gate (edits E0d's `lib/analytics/`); tests | frontend, qa-evals | ~380 | security-review |
| 11 | Web: Settings → Privacy (consents, requests, export, delete account, nominee); tests | frontend, qa-evals | ~350 | |
| 12 | Web admin: Privacy requests, Legal holds, Incidents; tests | frontend, qa-evals | ~390 | security-review |
| 13 | Infra: SNS alarms §8.4; `docs/runbooks/incident-and-breach.md` (CERT-In 6 h, DPDP without delay + 72 h, GDPR 72 h, restore-then-reapply, contacts, CERT-In form link); restore drill | infra | ~250 | needs-founder |

**Order:** 1 first for infra. 2 → 3 → 4. 5, 6, 7 after 2 (parallel; separate files, migrations sequenced by backend). 8 needs 6 and 7. 9 independent after 2. 10 needs 5 and E0d PR 10; 11 needs 5–8; 12 needs 6, 8, 9. 13 after 9 and 1. security-reviewer on every PR labelled so; product-reviewer at the end.

**File ownership:** backend `app/privacy/**`, `app/observability/logging.py`, migrations; ai-engineer `app/ai/gateway.py`, `app/ai/routing.py`; frontend `apps/web/app/(admin)/admin/{privacy,incidents}/**`, `apps/web/app/privacy/**`, `apps/web/content/privacy/**`, settings pages, `lib/analytics/consent.ts`; infra `infra/**`, `docs/data-map.md`, `docs/runbooks/**`; qa-evals tests. Notice **text** is written by the founders with counsel (Q-C9); frontend only places it.

---

## 11. Flags

- **needs-founder: yes.** Migrations (seven tables); login path (signup consent and age gate); approval path (DSR acknowledgements and breach notices through `approvals`); data deletion (purge, erasure); secrets (HMAC key, PostHog deletion key); spend (KMS, logs); legal positions (Part A) and residency decisions (§A.7).
- **security-review: yes.** Isolation (DSR, exports); masking (exports, logs, vault); IAM and KMS key policies; break-glass access; uploads (KYC prefix, export objects); third-party data flows (PostHog, Bedrock Global guard).
- `rules-change`: no.

---

## 12. Open questions

**For counsel (Q-C):**
1. Purposes and bases: confirm the purpose list (§2.2) and whether each is consent or a legitimate use under s.7(a). Is "AI processing outside India" a disclosure in the notice, or a separate consent?
2. Languages: is English + Hindi enough at launch under ss.5(3)/6(3)?
3. Rule 8(3): does the 1-year minimum retention of "personal data, traffic data and logs of the processing" require keeping chat **content** (AST) and deleted-account **profile** data for a year, or only processing logs and metadata?
4. Is an 18+ attestation adequate due diligence for a B2B platform, with no parental-consent flow?
5. Has any country been notified under s.16(1)? Does rule 15 affect Bedrock Global, PostHog EU or Meta?
6. GDPR Art. 27(2): does the occasional-processing exemption fit, or do we appoint an EU (and UK) representative before the first EU buyer?
7. Is direct sign-up by EU buyer staff to an India-based Orsyn a "transfer" needing SCCs, and which SCC module goes in buyer contracts?
8. Retention of consent records and DSR records: is 7 years right?
9. Confirm R1–R3 (CGST s.36, Companies Act s.128(5), Income-tax) and the "8 FY" rule; confirm SPDI Rules duties until 13 May 2027.
10. Aadhaar: confirm Orsyn may receive only a KYC provider reference and last 4 digits, with no Aadhaar Data Vault duty.
11. Commencement: confirm the dates in §1.1 against the e-Gazette (G.S.R. 843(E), 846(E)), and whether any later notification changed the phase-in.
12. Is the payment gateway a processor or an independent fiduciary for payer data?

**For founders (Q-F):**
1. Story key `DC`, milestone (M1 for PRs 1–4, which every story inherits?) and the proposed "Done when".
2. Approve 400-day prod / 180-day dev log retention (overrides E0d's 30/7).
3. Who is the CERT-In Point of Contact and the published privacy contact (rule 9)?
4. Approve the residency decisions in §A.7: Global for C1/C2, C3 never; PostHog EU opt-in with replay off.
5. WhatsApp: Meta Cloud API direct or which BSP?
6. Sarvam: confirm hosting region and DPA.
7. RFQs/drawings with no PO: is 3 years after last activity right?
8. Who adds the privacy screens to `docs/screens.md`?
9. Who drafts the notice text (EN, HI) with counsel, and by when (PR 10 waits on it)?
10. Separate AWS accounts for dev and prod (E0b Q11)? §2.9 relies on it.

---

## Appendix C — Gap audit of existing plans

Severity: **block** (must change before that plan's affected PR merges), **fix before build** (change the plan before the PR is built), **later**.

### C.1 E0 (being built now)

| Gap | Severity | Change |
| --- | --- | --- |
| Gateway cost log (`orsyn.ai.cost`) | none | Logs org_id, feature, model, prompt id/version, tokens, cost, latency, outcome; no message text. Compliant as is |
| `settings.py` | none | Env-only, no secrets. The `data_classes` field and residency guard arrive with E0b PR 3/4 (DC PR 4), not E0 |
| CI | none | No AWS credentials, no artifacts uploaded, eval reports git-ignored. Compliant |
| `.gitignore` | later | Optionally add `*.sql.gz`, `*.bak`, `exports/` when the first DB story adds dumps or exports. Not needed now |
| Gateway error chaining (`GatewayError … from last`) | later | When real providers land (E0b PR 4), provider exceptions must not carry prompt text into logs; covered by DC PR 3 |

**E0 needs no change. No E0 item is rated block.**

### C.2 E0b — admin, provider keys, routing

| Gap | Severity | Change |
| --- | --- | --- |
| Bedrock Global routes accept any data | fix before build (PR 3/4) | Add `data_classes` and `routing.residency`; refuse C3 on `global` (DC PR 4) |
| `events.client_ip` stored in append-only events | fix before build (E0c / PR 2) | Keep IPs in logs only (400-day retention), not in `events`; events are kept indefinitely and cannot be erased |
| `staff_admin.created` payload holds `{email, role}` | fix before build (PR 2) | Payload `{staff_id, role}`; email stays in `staff_admins` only |
| `admin.access_denied` actor `person:<email hash>` | later | Acceptable (pseudonymous); use a keyed HMAC, not a plain hash |
| No log retention or KMS on log groups set | fix before build (PR 9) | Adopt DC §2.7 / PR 1 settings |
| RDS/S3 encryption not specified | **block for whichever infra PR creates RDS/S3** | CMK encryption at creation (DC PR 1); cannot be retrofitted without restore |
| Data residency Q3 | decision | Answered by §A.7 |

### C.3 E0d — ops console and analytics

| Gap | Severity | Change |
| --- | --- | --- |
| **CloudWatch retention 30 days prod / 7 dev** (§9, PR 12) | **block** (PR 12) | 400 days prod, 180 days dev, KMS-encrypted (CERT-In Direction (iv); DPDP rules 6(1)(e), 8(3)) |
| Log masking filter covers email and phone only | fix before build (PR 2) | Use the shared `redact.py` (adds PAN, Aadhaar, IFSC, account numbers) and the allow-list formatter |
| PostHog "notice-only or opt-in" (Q7) | fix before build (PR 10) | **Opt-in**: init only after `product_analytics` consent; replay only after `session_replay` consent; replay off until counsel |
| PostHog erasure path | later (DC PR 8) | DSR erasure deletes the PostHog person; needs a scoped deletion key in Secrets Manager |
| PostHog DPA and Frankfurt disclosure | fix before build (PR 10) | DPA signed; listed in data map and notice |
| Side panel and console | later | Add Privacy and Incidents pages (DC PR 12) |
| `error_occurrences` 30-day prune | none | Fine: derived; source logs keep 400 days |
| Server-side PostHog events | fix before build (PR 11) | Send only for persons with `product_analytics` consent |
| SES region (Q6) | decision | SES in ap-south-1 |

### C.4 AST — assistant

| Gap | Severity | Change |
| --- | --- | --- |
| 90-day purge and hard delete of conversation content vs DPDP rule 8(3) 1-year minimum | fix before build (PRs 7–8) | Await Q-C3. If content must be kept: on delete/purge, move content to a restricted store for the remainder of 365 days, no product access, then delete; tell the user in the delete dialog |
| Sonnet answers via Global with user data | fix before build (PR 5) | Agents declare `data_classes`; tool projections drop C2 fields not needed (names, emails of colleagues); C3 never in tool output |
| `redact.py` duplicates DC's redactor | fix before build (PR 4) | Use the shared `app/privacy/redact.py`; AST keeps only assistant-specific checks in `validate.py` |
| Notice and consent | later | Add an "assistant" line to the notice purposes (legitimate use or consent per Q-C1) |
| DSR access export | later | Conversations included in the access export |

### C.5 KYC (plan not present on 2026-10-05)

When written, the KYC plan must: store PAN, bank account, IFSC and Aadhaar references only in `pii_vault`; never store an Aadhaar number (AA2); use an India-hosted provider with a DPA (§6.2); keep KYC images in the S3 `kyc/` prefix with 30-day expiry after decision; route any model step only through `in` routes with `C3` declared; and add its tables to the data map and erasure map. security-review and needs-founder apply.

---

## Appendix D — Proposed additions (text only, for founder approval)

### D.1 CLAUDE.md non-negotiables (proposed wording; do not apply without founder approval)

11. **Classify every field.** Every column is tagged C0 public, C1 business, C2 personal or C3 sensitive. C3 (PAN, bank account, Aadhaar reference, KYC images) lives only in `pii_vault` or the S3 `kyc/` prefix, never in logs, events, exports or fixtures, and never on a model route outside India. Aadhaar numbers are never stored.
12. **Logs are allow-listed.** Never log request or response bodies, headers, query strings, prompts or vendor error text. Logs stay in ap-south-1 for 400 days (prod).
13. **Consent and notice first.** Every purpose that touches personal data is in the privacy notice. Optional purposes (analytics, replay, marketing) run only after opt-in, and stop on withdrawal.
14. **Data map before first use.** A new store, processor or region is added to `docs/data-map.md`, with a signed DPA, in a `needs-founder` PR before any personal data flows to it.
15. **Delete by the registry.** Retention and erasure run only through `app/privacy/` jobs, respect legal holds, and keep legally required records restricted, not deleted.
16. **Incidents start a clock.** Anyone who notices a suspected breach alerts the founders at once and opens an incident; CERT-In within 6 hours, the DPDP Board without delay and in detail within 72 hours.
17. **No real personal data outside prod.** Dev, CI, local machines and the repo hold synthetic data only; prod data is never copied out.

### D.2 `docs/data-map.md` skeleton (infra writes it in DC PR 2)

```
# Data map
Owner: infra. Every row is checked when it changes and at least every 180 days.
Classes: C0 public · C1 business · C2 personal · C3 sensitive.

## Stores (Orsyn-controlled)
| Store | Env | Region | Classes | Encryption | Retention | Erasure path | Checked on |
| RDS Postgres orsyn-<env> | dev, prod | ap-south-1 | C0–C3 | KMS orsyn-<env>-data; pii_vault also orsyn-<env>-pii | per app/privacy/retention.py; backups 7 d | erasure executor + tombstones | |
| S3 orsyn-<env>-uploads (drawings, documents; kyc/ prefix) | | ap-south-1 | C1, C2, C3 (kyc/) | SSE-KMS data | per registry; noncurrent 30 d | erasure executor | |
| S3 orsyn-<env>-exports (DSR exports) | | ap-south-1 | C2 | SSE-KMS data | 7 d | lifecycle | |
| S3 orsyn-<env>-ops (eval reports) | | ap-south-1 | C0 | SSE-KMS data | 400 d | n/a | |
| S3 orsyn-<env>-logs (ALB, CloudTrail, flow logs) | | ap-south-1 | C2 (IPs) | SSE-KMS data | 400 d prod / 180 d dev | expiry | |
| CloudWatch Logs /orsyn/<env>/{api,worker,web} | | ap-south-1 | C2 (masked) | KMS data | 400 d / 180 d | expiry | |
| SQS queues + DLQs | | ap-south-1 | ids only | KMS data | 4–14 d | n/a | |
| Secrets Manager orsyn/<env>/* | | ap-south-1 | secrets | aws/secretsmanager | until rotated | n/a | |

## Processors
| Processor | Purpose | Classes | Region | Transfer basis | DPA | Checked on |
| AWS Bedrock (in. profiles) | Haiku-role agents | C1, C2, C3 allowed | India (Mumbai, Hyderabad) | n/a | AWS DPA | |
| AWS Bedrock (global. profiles) | Sonnet/Opus drawings, documents, assistant | C1, C2 only | any AWS commercial Region | DPDP s.16; disclosed | AWS DPA | |
| AWS SES | email | C2 | ap-south-1 | n/a | AWS DPA | |
| Sarvam | Indian languages, voice | C1, C2 | TBD | | TBD | |
| PostHog EU | product analytics (opt-in) | pseudonymous C2 | Frankfurt | DPDP s.16; consent | TBD | |
| Meta WhatsApp Cloud / BSP | messages | C2 | Meta cloud | DPDP s.16; disclosed | TBD | |
| KYC provider | identity, bank verification | C3 | India (required) | n/a | TBD | |
| Payment gateway | payments, payouts | payment refs, C3 | India (RBI) | n/a | TBD | |
| Google Workspace | staff identity | staff C2 | Google | | existing | |
| GitHub | code, CI | none (no personal data) | US | n/a | n/a | |

## Time source
ECS Fargate tasks use Amazon Time Sync Service (CERT-In FAQ Q42). Logs are UTC with Z.

## Tables
| Table | Classes | Retention category | Erasure action |
(one row per table; CI checks every table is listed)
```

---

## Sources opened (all on 2026-10-05)

- DPDP Act 2023, Gazette text (dpdpa.com/DPDPA_2023_official.pdf): ss.2, 3, 4, 5, 6, 7, 8, 9, 10, 11–15, 16, 17, 33, 44, Schedule.
- DPDP Rules 2025, G.S.R. 846(E) dated 13 Nov 2025, Gazette text (dpdpa.com/DPDP_Rules_2025_English_only.pdf): rules 1, 3, 6, 7, 8, 9, 10, 12, 13, 14, 15; First, Third and Fourth Schedules.
- DPDP Act commencement, G.S.R. 843(E), as quoted at dpdpa.com/dpdpa_enforcement_timeline.html (official copy not opened).
- CERT-In Directions No. 20(3)/2022-CERT-In, 28 Apr 2022, directions (i)–(iv), Annexure I; CERT-In FAQs (May 2022) Q13, Q24, Q29–Q31, Q35–Q37, Q40–Q44.
- RBI/2017-18/153, 6 Apr 2018, Storage of Payment System Data.
- GDPR Arts. 3(2), 27(1)–(2), 33(1), 46(1)–(2)(c) (gdpr-info.eu); European Commission adequacy decisions page.
- AWS: Bedrock cross-Region and Global cross-Region inference guides; Bedrock data protection; SES endpoints.
- PostHog: data storage docs (EU Cloud hosted in Frankfurt).
- Not opened (marked unverified): MeitY pages (403), UIDAI / Aadhaar Act (404, unreadable), CBIC CGST Act (404), Companies Act, Income-tax Act, SPDI Rules, GDPR Art. 12, UK GDPR.
