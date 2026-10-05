# Rules

Export and scheme requirements shown on the supplier roadmap. Rules live here, never in prompts. Each rule has a source and a checked date. The shape is defined in `schema.json` (JSON Schema 2020-12); CI validates every `*.json` rule file against it.

## Rule shape

| Field | Meaning |
| --- | --- |
| `id` | Stable slug, e.g. `eu-cbam` |
| `layer` | 1, 2 or 3 (see below) |
| `applies_to`, `market` | What and where the rule applies |
| `hs_prefixes` | HS code prefixes as digit strings; empty if not product-specific |
| `title`, `body` | Plain words a foundry owner understands; body 40 words or fewer (hard limit 320 characters) |
| `mandatory` | Required, or optional |
| `status_logic` | Code path that sets the roadmap status; currently only `always_todo` |
| `source` | `name`, `url`, `reference` (notification or section number), all required |
| `checked_on`, `review_by` | Dates, `YYYY-MM-DD` |
| `review_state` | `verified` or `awaiting_review` |

Unknown fields are rejected at every level. A rule that needs a new `status_logic` value is described to `backend`; the curator never edits code.

## Layers

1. Every exporter.
2. Product code and market.
3. Benefits and schemes.

## verified and awaiting_review

- `verified` only after a primary source has been opened and its reference recorded: DGFT, CBIC, GST portal, an EU regulation, or an official gazette.
- Secondary sources (news, consultancies, forums) can only create `awaiting_review`.
- Tax steps say "confirm with your CA". No legal advice.

## review_by

Every dated fact (a scheme end date, a tariff, a rate) gets a `review_by` date so it cannot go stale unnoticed. Past `review_by`, the rule needs a fresh check.

## Rates and amounts

Rates and amounts are stored as data with units (for example a percentage or INR per kg), never as numbers buried in body text. Code applies them. Models do no maths.

## Models and rules

A model explains a rule in the supplier's language. It never invents, changes or fills in a rule. New rules come from the curator with a source, or from `rules_watch` as `awaiting_review` proposals.

## Changing rules

Every change is a pull request labelled `rules-change`. The description lists the old and new text and the source opened, and `docs/rules-table.md` is updated with what changed and why.
