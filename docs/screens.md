# Screens

Build to this file, `.claude/agents/frontend.md` and the plan named under each screen. Add new screens as new `##` sections.

Shared rules for every screen below:
- Light theme, tokens from `frontend.md`. Archivo headings, Public Sans body. IBM Plex Mono for GSTIN, PAN, IFSC, Udyam, IEC, CIN and amounts. These values are never translated.
- One heading per screen, no intro paragraph. Status is coloured text with a word (ok / warn / bad plus the label), never a pill and never colour alone.
- Targets 44px or taller. Labelled inputs. Stepper and result rows announced to screen readers (`aria-live="polite"`).
- Dates en-IN, `05 Oct 2026, 14:32 IST`. The server sends UTC.
- Every string goes through the i18n catalogue. **Hindi: needed** for every string below unless marked "not translated".
- Sensitive-field rule: PAN, bank account, IFSC, GSTIN (it contains the PAN), Udyam, CIN, legal name, principal address and documents are never in URLs, logs, analytics or the service worker cache. Requests to `/v1/verification/*` use `Cache-Control: no-store`. No PostHog session replay and no autocapture of element text on `/s/verify*`, `/b/verify*` and `/admin/verification*`; all inputs are masked in any analytics.
- Masked GSTIN everywhere (screen, logs, support): "ends in 1Z5" (last 3 characters, which exclude the PAN). Never the 12th character or earlier.
- Items marked **pending founder** are open policy questions in `docs/plans/KYC-verification.md` §12. Build the default shown; make it a single config flag so the answer is a one-line change.

---

## KYC: supplier, buyer and staff verification

Plan: `docs/plans/KYC-verification.md` (§1.2 badges, §7 screens). Consent text: `docs/plans/DC-data-compliance.md` §7 (Settings, Privacy).

### K1. Supplier stepper `/s/verify` (390px)

Layout: top bar with back arrow and the heading "Verify your business". Under it a step tab row (Consent, GSTIN, Business, You, More, Bank), one tab per step, current one ink with a 2px accent underline, done steps with a check in ok colour. One short form per step, sticky bottom bar with the primary button (full width) and a text secondary button. Opens at the first incomplete step. State comes from `GET /v1/verification`. Back keeps typed values in memory for the session (see Storage rule below).

Common states per step:
| State | Behaviour |
| --- | --- |
| Loading | Skeleton rows for the form. Primary button shows "Checking…" and is disabled. No spinner longer than 10 s without the text "Still checking. You can close this page." |
| Error, provider down (503) | Inline, bad colour: "Verification is paused. We'll message you when it's back." Button becomes "Try again". |
| Error, network | "No connection. Your progress is saved on this phone. Re-enter your PAN and bank details when you retry." Retry. |
| Error, daily limit (429) | "You've reached today's limit. Try again tomorrow, or contact us." |
| Member, not owner | Read-only steps, banner row "Ask the account owner to finish this." No inputs. |

**Storage rule.** PAN, account number and IFSC are held in component memory only. Never localStorage, IndexedDB, sessionStorage, URLs or the service-worker cache; cleared on submit, step exit, tab hide for 5 minutes and unmount. Only these non-sensitive fields may persist on the phone: step reached, consent given (with notice version), GSTIN-confirmed flag, optional-toggle choices (Udyam, export). Typed GSTIN, names, addresses and numbers are not persisted; the server returns them after the check.

| Step | Purpose | Fields and copy | Primary / secondary | Validation | Masked |
| --- | --- | --- | --- | --- | --- |
| 1 Consent | Record consent for GST, PAN, MCA, DGFT, Udyam checks before any check runs | Heading of step: "Before we check". Rows: What we check / Who we ask ("GSTN, Income Tax, MCA, DGFT, Udyam, through our verification partner Cashfree") / How long we keep it / Your rights / Grievance contact. Link "Read the full notice". Notice text and version come from the API and are shown as returned. | "I agree" / "Not now" (returns to the home screen) | Button enabled only after the notice has loaded. 409 `stale_notice` reloads the notice and asks again. | n/a |
| 2 GSTIN | Get the GSTIN. Everything else is filled from it | Label "GSTIN". Mono input, 15 characters, auto-uppercase, no spaces, `inputmode="text"`, `autocapitalize="characters"`. Link "Use a photo of your GST certificate" (opens camera, K1a). | "Check GSTIN" / "Use a photo instead" | Checksum and shape checked in the browser as they type, hint at 15 characters: "This GSTIN doesn't look right. Check the last character." No call is sent until the checksum passes. Server errors: not active "GST shows this registration as Cancelled. Contact us." (shows the status returned); already linked "This GSTIN is already linked to another account. We'll look into it." (does not say which). | Shows "ends in 1Z5" after the check; the typed value is cleared from the field |
| 3 Business | Supplier confirms the data that came from GST | Rows, label left, value right: Legal name, Constitution, State, Principal address (all read-only, from GST, each with "from GST, 05 Oct 2026, 14:32 IST"). Editable: Trade name. Muted text "We found your PAN in your GSTIN." (no PAN characters shown). | "Yes, this is us" / "This is not us" (opens "Contact support") | Legal name is not editable. Trade name 2 to 80 characters. | PAN not shown. |
| 4 You | Confirm the signatory | Name (prefilled from login), Role as a radio list (Proprietor, Partner, Director, Designated partner, Karta, Authorised signatory). Only if the API answers `pan_needed`: "Your PAN" (mono, 10 characters, uppercase). Or "Upload an authorisation letter". | "Continue" / "Upload a letter instead" | PAN `AAAAA9999A`, 4th character checked in the browser. Roles are a closed list. | PAN field: `autocomplete="off"`, `autocorrect="off"`, `spellcheck="false"`, `type="text"` with CSS/visual masking (e.g. `-webkit-text-security: disc`) and a show toggle. Not `type="password"`, so password managers never offer to save it. Never echoed back. |
| 5 More | Optional registrations | Three rows, each a toggle with a field: "I have a Udyam registration" (mono `UDYAM-XX-00-0000000`, auto-uppercase), "I export" (no field, "We'll check your IEC with your PAN"), "CIN or LLPIN" (shown only when constitution is a company or LLP, prefilled if returned). | "Continue" / "Skip for now" | Udyam shape, CIN 21 characters, LLPIN `AAA-0000`. Each row shows its own result inline: Verified in ok colour, "Not found" in warn with "Edit". | none |
| 6 Bank | Verify the payout account. Can be skipped, required before the first payout | Option A (default, **pending founder Q12**): "Pay ₹1 from your business account by UPI". Shows QR and a "Open UPI app" link. Note row: "Use the account you want to be paid in. Refund: as the bank partner's rules" (final wording after Q12). Option B: "Type account details": Account number (`inputmode="numeric"`, `autocomplete="off"`, visually masked like PAN, not `type="password"`), Re-enter account number (same), IFSC (mono, auto-uppercase, 11 characters), bank name shown under the field once the IFSC is valid. Option C: "Photo of a cancelled cheque" (K1a pattern). | A: "I've paid" / B: "Verify account" / "Do this later" | Account number 9 to 18 digits, both entries must match (no paste in the second field), IFSC `^[A-Z]{4}0[A-Z0-9]{6}$`. Mismatch: "Your bank shows the name as R*** E*********. We'll review it within 2 working days." (first letters only). Not found: "The bank couldn't find this account." | Account number masked to last 4 after submit. Never shown again in full to anyone in the app. |
| 7 Done | Hands over to K2 or K3 | Redirect to `/s/verify/status` | | | |

Waiting on UPI: "Waiting for your payment. This can take a minute." Poll every 3 s for up to 5 minutes, then "We haven't received it. Try again" and a new QR.

#### K1a. Photo of a document: result rows (Mercury pattern)
Used for the GST certificate (step 2) and the cancelled cheque (step 6). Never calls the API until the supplier taps "Use these".

1. Camera or file picker. Accepts JPG, PNG, PDF, up to 10 MB. Under the control: "JPG, PNG or PDF, up to 10 MB". Wrong type or size: "This file type isn't accepted" or "This file is too large" before upload.
2. Loading: thumbnail with file name and "Reading your document…".
3. Result card (hairline border, 8px radius): a heading row with the file name and a result line in ok or warn colour, then one row per field, label left, value right in mono where it applies, with a status word at the far right.

| Row (GST certificate) | Found | Not found |
| --- | --- | --- |
| GSTIN | `27AAAAA0000A1Z5`, editable, "Found" in ok | "Not found. Type it below." in warn |
| Legal name | value, "Found" | "Not found" (not blocking: GST fills it) |
| Trade name | value, "Found" | "Not found" (not blocking) |
| Checksum | "Valid" in ok | "This GSTIN doesn't look right" in bad, blocks "Use these" |

Cheque rows: Account number, IFSC, Account holder name, same pattern. Low-confidence or unreadable fields show "Check this" in warn with the field editable.
Actions: **"Use these"** (primary) and **"Try another photo"**. If nothing was read: "Couldn't read it. Type the GSTIN instead." Fields are always editable. The result is a proposal; nothing is verified until the server check passes after "Use these".

### K2. Status `/s/verify/status` (390px)

Heading "Verification". Sections in order, each a hairline card with label-left, value-right rows. Loading: skeleton cards. Error: "Couldn't load your verification." + Retry. Empty (not started): one card, "You haven't started." with the button "Start verification".

**Checklist (Acctual pattern).** First card, "What we need". One row per requirement with a check (ok colour, done), a dash (muted, optional), or an empty circle (warn, to do). Under each row, in muted text, what is accepted:
| Row | Done when | Accepted under it |
| --- | --- | --- |
| GSTIN | GST check passes | "Type it, or photo of your GST certificate" |
| PAN | derived from GSTIN | "Taken from your GSTIN" |
| Signatory | confirmed | "Your name matches GST, or your PAN, or an authorisation letter" |
| Bank account | verified | "UPI payment of ₹1, account number and IFSC, or cancelled cheque" |
| Udyam, IEC, CIN or LLPIN | optional, shown as "Optional" | "Number only" |
Each unfinished row is a link to its step. Rows in review show "In review" (warn).

**Badges.** Row per badge, label left, state right as coloured text:
| State | Text | Colour | Note under the row |
| --- | --- | --- | --- |
| Verified | "Verified" | ok | "Checked 05 Oct 2026, 14:32 IST. Next check by 04 Nov 2026." |
| In review | "In review" | warn | "We'll tell you within 2 working days." |
| Due | "Due on 04 Nov 2026" | warn | "We'll check again. You don't need to do anything." or a button when the supplier must act |
| Lapsed | "Lapsed" | bad | "Buyers can't see this badge. Fix: <action>" with a button |
Badges: Verified supplier, GST, PAN, MSME (Udyam), Company (MCA), Export-ready (IEC), Bank. Not-started badges are not listed.

**What's due.** Rows from `recheck_due` with the due date. Empty: "Nothing due." in ok colour.

**Documents.** Row per document: type, uploaded date, "View" (opens in a new tab, link valid 60 s) and "Delete". Delete confirms: "Delete this document? Your badges stay as they are." Blocked with "Needed for a review that is open" when the server returns 409. Empty: "No documents kept."

**Consents.** Row per purpose with the date given and "Withdraw". The confirm sheet lists what happens, using the server's `effects` text before the call, for example "Bank verified badge removed; payouts will need a new consent." Buttons "Withdraw" and "Keep".

**Your data.** Rows "Download my data", "Correct my details", "Delete my data". Each opens a short form (optional note) and then shows the request with its due date. Empty: "No requests." Delete explains what is kept by law and for how long.

### K3. In review (end state, 390px)

Shown on the status page in place of the checklist when any case is open, and as the screen after step 7. Plain, no illustration, no photo.
- Heading: "We're checking your details".
- Rows: Status "In review" (warn); Opened "05 Oct 2026, 14:32 IST"; Expected "By 07 Oct 2026, 18:00 IST" (the server's `sla_due_at`: 2 IST working days); Reference (mono, short id).
- Under "What happens next": three short lines. "We check your details against official records." / "You get a message here and on WhatsApp when it's done." / "If we need a document, we'll ask for it here."
- Buttons: "Back to home" (primary), "Contact us" (secondary).
- The reason for the review is never shown (buyer screening and sanctions cases especially). If staff asked for a document, a warn row "We need one more document: Cancelled cheque" with an "Upload" button replaces the "Expected" row.
- Past the due time: "This is taking longer than usual. We're on it." Never a count-down.
- Error: "Couldn't load your status." + Retry.

### K4. Buyer: badges and detail sheet (desktop 1440px; the sheet is a right drawer, a bottom sheet on phones)

Where: supplier card, quote comparison, showcase page.
- Badge row: icon plus label text, ink-2 for verified. No colour-only meaning. Max four shown, then "+3 more" opens the sheet. Badge labels: Verified supplier, GST verified, PAN verified, MSME registered, Company registered, Export-ready (IEC), Bank verified. Hindi: needed.
- Empty (unverified supplier): **pending founder Q2.** Default: muted "Verification in progress". Alternative: show nothing.
- Error or loading: the badge area is hidden and the card renders without it.
- Sheet heading is the badge name. One card per source check, label left, value right: Checked "GSTIN", Source "GSTN", Through "Cashfree", Checked on "05 Oct 2026, 14:32 IST", Next check by "04 Nov 2026", Reference "…A1B2C3" (last 6, mono). GST badge may add "Returns filed: last 12 months" as a fact, not a pass or fail (**pending founder Q2**).
- Shown: trade name. **Legal name, GSTIN, PAN, street address, bank details and contact details are never shown before award.** Legal name is shown only on the order after award (**pending founder Q10**: trade name on the showcase, legal name after award is the default).
- Sheet states: loading skeleton; error "Couldn't load this check." + Retry; badge gone since the page loaded: "This badge is no longer active."
- Buyer's own verification `/b/verify`: same step components as K1 (Consent, GSTIN, Business). Foreign buyer: consent, company name, country, registry number, website, upload registry extract, then the in-review end state K3. A screening hold shows the K3 text only; no reason.

### K5. Admin verification (desktop 1440px, ops console, side panel item "Verification")

**Queue `/admin/verification`.** Heading "Verification". Filters: reason, state, org (labelled selects). Table (TanStack): Org, Reason, Opened, SLA due, State. SLA due in warn when past, in bad over a day past. Row opens the case. Empty: "No reviews waiting." in ok. Loading: skeleton rows. Error: message + Retry.

**Case `/admin/verification/[id]`.** Heading is the org name. Two columns.
- Left: Checks timeline (type, outcome as coloured text, source, provider ref, checked on). Names side by side: GST legal name, name at bank, name typed, each with the match level. Sanctions candidates (list, entry ref, matched name, score, programmes, link to the official entry). Documents list with "View" (owner only), which asks for a reason code and note and opens in a new tab for 60 s.
- Right: Org card (masked values; "Reveal" needs the reason dialog, 15 minutes), consent state, current badges. Decision form: Approve, Reject, Request info. Note required (10 to 500 characters), sent as typed. Request info uses a fixed document-type picker, not free text to the supplier.
- Viewers see everything except View, Reveal and the decision form (disabled with "Owner only").
- States: loading skeleton; 409 "Already decided by <name> at <time>" with a reload; per-action inline errors; 429 on views "Daily limit reached".
- Not in this pass: lists, data requests and stats screens (plan §7.4).

### Spec decisions made here (for founder review)
- Step tabs replace a progress bar; "one question per screen" is relaxed to one short form per step.
- Buyer badges are text plus icon, not pills or chips.
- PAN is masked on screen even though the user typed it, with CSS masking rather than a password field.
- UPI bank option is listed first only as the pending-founder default; swap is a config flag.
