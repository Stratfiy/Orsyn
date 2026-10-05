# Orsyn — read this first

Orsyn (working name) is an AI-native supply network on verified Indian suppliers. Buyers send an RFQ from a drawing and get verified quotes, documents and delivery handled. Suppliers join free on WhatsApp or web and get a showcase page, an export roadmap with benefits, and AI-drafted quotes.

Phase 1 milestones, in order: **M1 First RFQ loop → M2 Award and first PO → M3 Negotiation → M4 First export order → M5 Receipt and close.** The story list with "Done when" lives in `docs/build-plan.md`; screens in `docs/screens.md`.

## Non-negotiables (every agent, every PR)

1. **Agents propose, people approve.** Nothing an agent drafts (RFQ, quote, message, document) leaves the platform without a person's action, recorded in `approvals`.
2. **Numbers in code, never in a model.** Prices, totals, taxes, duties, benefit amounts and emissions are computed in code from stored data. Models extract and suggest; they never calculate money.
3. **Every number traces to its source.** Each figure shown links to the quote version, document line or rule it came from.
4. **Rules live in `packages/rules`, never in prompts.** Export and scheme requirements carry a source and a checked date. A model explains a rule; it never invents one.
5. **Contacts hidden until award.** Supplier phone, email and website stay masked in the API, logs, exports and prompts until a buyer awards an order. A supplier's own customers are never masked.
6. **Never sold:** ranking in matches, placement, buyer contacts.
7. **Every document line links to its PO line** (the order ontology).
8. **One model gateway.** Every Claude or Sarvam call goes through `services/api/app/ai/gateway.py`, which logs customer, feature, model, tokens and cost.
9. **Tenant isolation.** Every query is scoped by `org_id`; every endpoint checks it; tests prove it.
10. **Nothing from any employer** enters this repo: no code, documents, data, vendor lists or templates. Fixtures are real samples shared by suppliers or buyers with their consent, with personal details removed.

## Stack

- Services: Python 3.12, FastAPI, Pydantic v2, PostgreSQL 16 + pgvector, pytest. ORM and migrations as named in `docs/architecture.md` (if not named: SQLAlchemy 2 + Alembic). Dependencies with `uv` and `pyproject.toml`.
- Web: TypeScript (strict), Next.js 15 App Router, Tailwind, TanStack Query and Table, Zod. Supplier side is a mobile-first PWA.
- AWS Mumbai (ap-south-1): ECS Fargate, RDS Postgres single-AZ, S3 (private), SQS and EventBridge Scheduler for background and scheduled jobs (no Temporal until Phase 2), Secrets Manager.
- Models (Veeru confirms routing): Sonnet for drawings and documents, Opus when confidence is low; Haiku for masking, matching and alerts; Sarvam for Indian languages and voice.

## Layout

```
apps/web/               buyer app + supplier PWA
services/api/app/
  domain/               ontology: orgs, parts, RFQs, quote versions,
                        PO lines, shipments, documents, GRN, match, events
  modules/              suppliers, buyers, rfq, matching, quoting,
                        orders, documents, roadmap, benefits
  ai/
    gateway.py          the only way to call a model
    agents/             one job each: profile_codes, rfq_from_drawing,
                        quote_draft, doc_check, rules_watch, masking
    prompts/            versioned prompt files
    tools/              gst_lookup, hsn_search, whatsapp, storage
  approvals/            every outbound action waits here for a person
  jobs/                 SQS consumers and schedules
services/api/migrations/
packages/rules/         rules table JSON (source + checked date per rule)
evals/<agent>/          cases, expected outputs, runner, scores
tests/                  unit, API and end-to-end tests; fixtures/
infra/                  AWS as code
docs/                   brief, build-plan, screens, architecture,
                        rules-table, plans/ (one design plan per story)
```

## The team (subagents in `.claude/agents/`)

| Agent | Role | Writes |
| --- | --- | --- |
| architect | Tech lead. Design plan before any non-trivial story | `docs/plans/` only |
| backend | Services, schema, migrations, ontology, approvals, jobs | `services/api/` |
| frontend | Buyer app and supplier PWA to the screen specs | `apps/web/` |
| ai-engineer | Gateway, agents, prompts, tools, evals for agents | `services/api/app/ai/`, `evals/` |
| rules-curator | Export and scheme rules with sources | `packages/rules/`, `docs/rules-table.md` |
| qa-evals | Tests for every "Done when" clause, eval runs | `tests/`, `evals/` |
| infra | AWS, CI, cost | `infra/`, `.github/` |
| security-reviewer | Reviews auth, isolation, masking, uploads, secrets | nothing (read-only) |
| product-reviewer | Checks the work against the story, screens and rules | nothing (read-only) |

## How a story flows

1. **Plan.** `architect` writes `docs/plans/<KEY>-<slug>.md`. Stop and ask for approval when the plan is labelled **needs-founder** (migrations, login or approval paths, secrets, spend) or touches more than one module.
2. **Build.** The agents the plan names implement it. Run them in parallel only when their files don't overlap. Keep each PR under about 400 changed lines; split otherwise.
3. **Test.** `qa-evals` adds a test per "Done when" clause plus the negative tests (masking, isolation, approvals). Agent changes also run their evals against the pass marks.
4. **Review.** `security-reviewer` is required when the change touches login, `org_id` scoping, approvals, masking, uploads, webhooks, secrets, IAM or payments. `product-reviewer` checks every story.
5. **PR.** Use the PR template. Veeru reviews and merges. Nithish checks it the same day. Every real case Nithish brings becomes a permanent fixture or eval case.

## Pass marks (evals block the PR when missed)

- Code suggestions: at least 80% of HSN/SAC codes right with no edits.
- RFQ from a drawing: material, dimensions, quantity, tolerances and standards at least 90% right.
- Quote drafts: sendable with two edits or fewer.
- Export roadmap: zero wrong mandatory steps.
- Cost: every eval run reports AI cost per case.

## Labels

`needs-founder` · `security-review` · `rules-change` · `M1`…`M5`

## Don'ts

- No dark theme. No gradients, emoji, sparkles or "AI-powered" copy in the UI.
- No model call outside the gateway. No money maths in prompts.
- No real personal data in fixtures, logs or prompts beyond what the task needs.
- No production deploys or data deletion without an approved `needs-founder` PR.
