# E0 — Repo, CI and environments

Status: draft, waiting for founder OK. Author: architect. Date: 2026-10-05.

Inputs read: `CLAUDE.md`, `KICKOFF.md`, `.claude/agents/*`, `.github/pull_request_template.md`, `.claude/settings.json`, `README.md`.
**Missing:** `docs/build-plan.md`, `docs/screens.md` and `docs/architecture.md` do not exist. The story text and "Done when" come from `KICKOFF.md`. E0 creates stubs for all three (see §1.4); the founders write the content.

---

## 1. Goal

Give the monorepo its skeleton, tooling and a CI pipeline that blocks merges on lint, type-check and tests for api and web. Add a deploy-to-dev job that is documented but switched off until the AWS account exists.

> Done when: every PR runs tests; merges deploy to dev automatically.

E0 meets the first clause in full. The second is met **structurally only**: the deploy job exists, is skipped, and needs one reviewed PR to switch it on (§3.4).

**Deliberately not building:** Dockerfiles, docker-compose/Postgres, Alembic/migrations, IaC under `infra/`, Playwright/e2e, PWA manifest, i18n, coverage gates, CodeQL, Dependabot/Renovate, pre-commit hooks, auth, a real model provider. No feature code.

### 1.1 Layout: what E0 creates now and what comes later

| Path | E0 | Contents in E0 |
| --- | --- | --- |
| `apps/web/` | now | Next.js 15 app shell, placeholder home, tests |
| `services/api/app/` | now | `main.py`, `settings.py`, `ai/` (gateway + fake provider) |
| `services/api/tests/` | now | api tests (see §1.3) |
| `services/api/app/{domain,modules,approvals,jobs}/`, `ai/{agents,prompts,tools}/` | later | created by the first story that needs them; no empty dirs or `.gitkeep` |
| `services/api/migrations/` | later | first story that adds a table (needs-founder) |
| `packages/rules/` | now | `schema.json`, `README.md`; no rules |
| `evals/` | now | `runner.py`, `README.md`, `_smoke/cases.jsonl` (fake provider only) |
| `tests/` (root) | later | e2e and shared `fixtures/` once there is a flow to test |
| `infra/` | later | after the IaC tool is chosen (Q1) and the AWS account exists |
| `docs/` | now | stubs for `build-plan.md`, `screens.md`, `architecture.md` + this plan |
| `.github/workflows/ci.yml` | now | CI + disabled deploy job |

### 1.2 Tooling and versions

| Area | Choice | Pinned where |
| --- | --- | --- |
| Python | 3.12 | `services/api/.python-version`, `requires-python = ">=3.12,<3.13"` |
| Python deps | `uv`, `pyproject.toml` + committed `uv.lock`, build backend `hatchling` (so `app` installs editable and `evals/` can import it) | `services/api/pyproject.toml`; uv version pinned in CI (`setup-uv` `version:`) |
| api runtime deps | `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `pydantic-settings` | |
| api dev deps | `pytest`, `httpx` (TestClient), `ruff`, `mypy`, `jsonschema` (rules schema test) | `[dependency-groups] dev` |
| Node | 24 LTS (Active LTS; 22 is in maintenance) — Q3 | `.nvmrc` = `24`, root `package.json` `engines.node = ">=24 <25"` |
| pnpm | 10.x, exact patch fixed at build time | root `package.json` `"packageManager": "pnpm@10.<x>.<y>"`; CI reads it via `pnpm/action-setup` |
| Workspace | `pnpm-workspace.yaml`: `packages: ["apps/*"]` | committed `pnpm-lock.yaml` |
| Web | Next.js 15 App Router, React 19, TS strict (+ `noUncheckedIndexedAccess`), Tailwind v4 (tokens in CSS `@theme`), fonts via `next/font/google` (self-hosted at build, no runtime Google calls) | `apps/web/package.json` |
| Web lint/format | ESLint 9 flat config with `eslint-config-next` (not `next lint`, which is deprecated); Prettier + `prettier-plugin-tailwindcss` | |
| Web tests | **Vitest + Testing Library + jsdom** | |

**Why Vitest:** native TS/ESM with no Babel or SWC-jest config, Jest-compatible API, fast watch, documented by Next.js. Limit: it cannot render async Server Components, so unit tests cover client components and pure functions; server-rendered flows get Playwright later (not E0).

TanStack Query/Table and Zod are **not** installed in E0 — nothing uses them yet.

### 1.3 Where tests live (deviation from CLAUDE.md)

CLAUDE.md puts tests in a root `tests/`. Decision: **api tests in `services/api/tests/`, web tests in `apps/web/tests/`**. Root `tests/` stays reserved for e2e and shared `fixtures/`.
Reason: each tool then runs from its own project root with default discovery. pytest uses the uv venv; Vitest resolves `node_modules` from `apps/web`. A root `tests/web/` would break pnpm's module resolution, and a root `tests/api/` would need its own ruff/mypy config. CI finds tests by default discovery: `testpaths = ["tests"]` in pyproject, and `include: ["tests/**/*.test.{ts,tsx}"]` in `vitest.config.ts`. Asks the founder to amend the CLAUDE.md layout line (Q5). qa-evals still owns every test file.

### 1.4 Docs skeleton (stubs only)

`docs/build-plan.md` (milestones M1–M5 headings + an E0 entry with its "Done when"), `docs/screens.md` (heading + "to be written"), `docs/architecture.md` (headings: Stack, ORM and migrations = "SQLAlchemy 2 + Alembic unless changed", IaC = "TBD, see E0 Q1", Environments). Each ≤ 15 lines, no invented product content. Written by infra.

### 1.5 Commands

All are run from the repo root. CI runs exactly these.

**api** (`cd services/api`):
```
uv sync --frozen
uv run ruff format --check . ../../evals
uv run ruff check . ../../evals --config pyproject.toml
uv run mypy                       # [tool.mypy] strict = true, files = ["app", "tests", "../../evals"]
uv run pytest                     # testpaths = ["tests"], -q, --strict-markers
uv run python ../../evals/runner.py --suite _smoke   # fake provider, no network
```
Ruff: `line-length = 100`, `select = ["E","F","I","B","UP","S","N","SIM"]`, `S101` ignored in `tests/`.

**web** (`pnpm --filter web <script>`; scripts in `apps/web/package.json`):
```
pnpm install --frozen-lockfile
lint        eslint . --max-warnings 0
format      prettier --check .
typecheck   tsc --noEmit
test        vitest run
build       next build
```
**Root conveniences:** root `package.json` scripts `lint`, `typecheck`, `test`, `build` → `pnpm -r <script>`. A root `Makefile` with `api-check`, `web-check`, `check` (both), `api-dev` (`uv run uvicorn app.main:app --reload`), `web-dev`. It is the single place README points to.

## 2. Ontology impact

None. No tables, no migrations. The gateway's cost record goes to structured logs only in E0. A `model_calls` table (with `org_id`, `created_at`, `created_by`) belongs to the first story with a real agent.

## 3. API

### 3.1 `GET /health`
- No auth, called by anyone (load balancer, CI smoke). No DB check (there is no DB yet).
- 200 → `{"status": "ok", "version": "<ORSYN_GIT_SHA or 'dev'>", "env": "<local|dev|prod>"}`.
- No other endpoints. OpenAPI docs stay on in `local` and `dev`, and off in `prod` (setting-driven).

### 3.2 Settings (`app/settings.py`, pydantic-settings)
`env_prefix = "ORSYN_"`, reads the environment (and `.env` locally; never committed).
| Var | Type | Default |
| --- | --- | --- |
| `ORSYN_ENV` | `Literal["local","dev","prod"]` | `local` |
| `ORSYN_LOG_LEVEL` | str | `INFO` |
| `ORSYN_GIT_SHA` | str | `dev` |
| `ORSYN_AI_PROVIDER` | `Literal["fake"]` | `fake` (only allowed value in E0) |

No secrets are needed in E0. `services/api/.env.example` lists these four with their defaults.

### 3.3 Gateway interface (`app/ai/gateway.py`) — ai-engineer
- `ModelRequest` (Pydantic): `org_id`, `feature`, `model`, `prompt_id`, `prompt_version`, `messages`, `max_tokens`, `timeout_s`.
- `ModelResponse`: `text`, `model`, `input_tokens`, `output_tokens`, `cost_usd: Decimal`, `latency_ms`.
- `ModelProvider` Protocol: `complete(req) -> ProviderResult`. `FakeProvider` in `app/ai/fake_provider.py` is deterministic: it echoes the input and counts tokens by whitespace.
- `Gateway.complete(req)`: calls the provider with a timeout and one retry on `ProviderError`, computes cost **in code** from a `PRICES` table (Decimal per 1M tokens; the fake model costs 0), and emits one structured log record on logger `orsyn.ai.cost` with org_id, feature, model, prompt id/version, tokens, cost and latency. The record never includes message text.
- `get_gateway()` builds from settings. There is no import of any vendor SDK anywhere.

### 3.4 CI workflow (`.github/workflows/ci.yml`) — infra

| Item | Decision |
| --- | --- |
| Triggers | `pull_request` (all branches → `main`), `push` to `main`, `workflow_dispatch` |
| Permissions | top level `permissions: contents: read`; nothing else. `deploy-dev` adds `id-token: write` at job level only when enabled |
| Concurrency | `group: ci-${{ github.ref }}`, `cancel-in-progress: ${{ github.event_name == 'pull_request' }}` (never cancel a main run mid-deploy) |
| Path filters | **None.** Both jobs run on every PR (each ~2–3 min). With branch protection, path-filtered required checks never report and block merges. Revisit when CI exceeds ~5 min |
| Actions | `actions/checkout`, `astral-sh/setup-uv`, `actions/setup-node`, `pnpm/action-setup` — each **pinned to a full commit SHA** with a `# vX.Y.Z` comment. Infra looks up the SHAs at build time; none are invented here. `persist-credentials: false` on checkout |
| Runner | `ubuntu-24.04` (pinned, not `-latest`), `timeout-minutes: 10` per job |
| Job `api` | setup-uv (`enable-cache: true`, cache key on `services/api/uv.lock`, Python from `.python-version`) → the §1.5 api commands |
| Job `web` | pnpm/action-setup → setup-node (`node-version-file: .nvmrc`, `cache: pnpm`) → the §1.5 web commands. Also caches `apps/web/.next/cache` keyed on the lockfile |
| Job `deploy-dev` | see below |
| Required checks | `api`, `web`. Job ids must stay stable for branch protection |

**`deploy-dev` (disabled placeholder)**
- `needs: [api, web]`, `environment: dev`, `if: false  # E0: disabled until AWS account exists — enabling is a needs-founder PR`.
- A hard-coded `if: false` is chosen over a repo variable so that switching it on goes through a reviewed PR.
- A header comment documents what it will do: on `push` to `main` only →
  1. `aws-actions/configure-aws-credentials` via **OIDC** (`role-to-assume: ${{ vars.AWS_DEV_DEPLOY_ROLE_ARN }}`, `aws-region: ap-south-1`); no access keys.
  2. `aws-actions/amazon-ecr-login`.
  3. Build and push `orsyn-api` (and `orsyn-web`, Q6) images tagged with `${{ github.sha }}`.
  4. `amazon-ecs-render-task-definition` + `amazon-ecs-deploy-task-definition` to the ECS Fargate dev cluster, `wait-for-service-stability: true`.
  5. `curl` the dev `/health` and check that `version` equals the SHA.
- Prerequisites, listed in the comment: AWS account, GitHub OIDC provider + a deploy role restricted to `repo:<org>/Orsyn:environment:dev`, ECR repos, ECS cluster/services, Dockerfiles, and a GitHub `dev` environment. All are later stories, all `needs-founder`.

### 3.5 `.gitignore` — infra
```
# env and secrets
.env
.env.*
!.env.example
*.pem
*.key
secrets/
# python
__pycache__/
*.py[cod]
.venv/
.mypy_cache/
.ruff_cache/
.pytest_cache/
.coverage
htmlcov/
# node / next
node_modules/
.next/
out/
*.tsbuildinfo
next-env.d.ts
.pnpm-store/
coverage/
# local data and large fixtures
data/
*.sqlite
*.db
*.dump
tests/fixtures/large/
evals/**/reports/
**/*.dwg
**/*.step
**/*.stp
# build and tooling
dist/
build/
.terraform/
*.tfstate*
.DS_Store
.idea/
.vscode/*
!.vscode/extensions.json
```
Drawing and fixture files over ~1 MB go to S3 (qa-evals rule). `*.pdf` is not ignored, because small consented fixtures may be PDFs.

### 3.6 GitHub labels — infra (needs repo admin)
`gh label create` for: `needs-founder` (#B42318), `security-review` (#B45309), `rules-change` (#1F4FD8), `M1`…`M5` (#5B6470). The commands are listed in README under "Repo setup", because labels are not files.

## 4. Events

None. There is no event log yet. The gateway's `orsyn.ai.cost` log line is not an ontology event.

## 5. AI agents

None. E0 ships only the gateway interface, `FakeProvider` and cost logging (§3.3). There are no prompts and no prompt files. The `evals/` runner skeleton:
- `evals/runner.py --suite <name>` reads `evals/<suite>/cases.jsonl` (`{"id","input","expected"}`), runs each case through `Gateway` with `FakeProvider`, and scores by exact match. It writes `evals/<suite>/reports/<UTC timestamp>.json` with score, pass mark and cost per case (0), and exits non-zero below the pass mark.
- `evals/_smoke/cases.jsonl`: 2 cases, which prove the wiring in CI. Real agents add `evals/<agent>/` later with the CLAUDE.md pass marks.

## 6. Rules

None read. rules-curator writes `packages/rules/schema.json` (JSON Schema 2020-12 for the rule shape in `rules-curator.md`):
- `id` slug.
- `layer` ∈ {1, 2, 3}.
- `applies_to`, `market`, `hs_prefixes` (digit strings).
- `title`.
- `body` (≤ 40 words is the guideline; `maxLength` 320).
- `mandatory`, `status_logic` (enum, starting `["always_todo"]`).
- `source{name,url,reference}` all required.
- `checked_on` and `review_by` (`format: date`).
- `review_state` ∈ {`verified`, `awaiting_review`}.
- `additionalProperties: false`.

`packages/rules/README.md` explains the shape, the layers, verified vs awaiting_review, and that rates are data with units. No rules ship.

## 7. Screens

`docs/screens.md` does not exist, so frontend builds only to `frontend.md`:
- **Tokens** in `app/globals.css` `@theme`: ink, ink-2, muted, line, canvas, accent, ok, warn, bad (exact hex from `frontend.md`), 8px card radius.
- **Fonts:** Archivo (headings), Public Sans (body), IBM Plex Mono (`font-mono`, codes/numbers).
- **App shell** (`components/shell/`):
  - `AppShell` places the panels on the grey canvas.
  - `SidePanel` is a rounded white panel that collapses to icons. Its toggle is a real `<button>` with `aria-expanded`, and the collapsed state is kept in `localStorage`. Below 768px it becomes a drawer. Its nav items are placeholders ("Home" only).
  - `TopBar` is a rounded white bar with the product name and nothing else.
- **Placeholder home** `app/page.tsx`: one `h1` "Home" and one line of plain copy. Light theme only; no gradients, emoji or AI copy.
- **States:** `app/loading.tsx` (skeleton lines), `app/error.tsx` (plain message + retry button), `app/not-found.tsx`. The home's "empty" state is the placeholder itself.
- Checked at 390px and 1440px. Touch targets are 44px.

## 8. Tests and evals (qa-evals)

| "Done when" clause | Proof |
| --- | --- |
| every PR runs tests | `ci.yml` runs `pytest`, `vitest run`, ruff, mypy, eslint, tsc on `pull_request`. Verified by opening the E0 PR itself: checks `api` and `web` appear and are green. A deliberately failing test on a throwaway branch shows red (manual check, described in the PR) |
| merges deploy to dev automatically | Deferred: `deploy-dev` job present, `if: false`, shows as "skipped" on the main run. Manual check: the job is visible in the run graph |

api tests (`services/api/tests/`):
- `test_health.py`: 200 and the response shape.
- `test_settings.py`: defaults; env override; invalid `ORSYN_ENV` rejected; `ORSYN_AI_PROVIDER=openai` rejected.
- `ai/test_gateway.py`: the fake call returns tokens and Decimal cost; one cost log record with all fields and **no message text**; retries once then raises a typed error; timeout honoured.
- `test_no_direct_model_calls.py`: scans `app/` and fails if `anthropic`, `openai` or a `sarvam` import appears outside `app/ai/`.
- `test_rules_schema.py`: `schema.json` passes `Draft202012Validator.check_schema`; every `packages/rules/*.json` validates (none yet); a sample valid rule passes and one missing `source` fails.

web tests (`apps/web/tests/`):
- `shell.test.tsx`: renders the side panel and top bar; toggle flips `aria-expanded`.
- `home.test.tsx`: exactly one `h1`.
- `error.test.tsx`: the retry button calls `reset`.

Negative tests for masking, `org_id` isolation and approvals: **not applicable** (no data, no endpoints beyond `/health`). State this in the PR. Tests are deterministic, with no network and no model calls.

Evals: the `_smoke` suite runs in CI with pass mark 100% and cost 0.

## 9. Cost

- **Model calls per user action: 0.** The fake provider only. Cost-logging feature name for the smoke suite: `eval_smoke`.
- **CI:** about 5–6 runner-minutes per push (api ~2, web ~3). Within GitHub's included minutes on a private repo's plan, the cost is ₹0/$0. Overage is billed per Linux minute; confirm the plan (Q8).
- **AWS: ₹0/$0** (no account).
- **Expected monthly cost change: ₹0 / $0.**

## 10. PR split

**Honest size estimate** (changed lines, lockfiles excluded):

| Part | Lines |
| --- | --- |
| api + CI + repo hygiene + docs stubs | ~430 |
| gateway + evals + rules schema + their tests | ~420 |
| web scaffold + tokens + harness | ~300 |
| shell + tests | ~240 |
| **Total** | **~1,400** |

The lockfiles add a lot on top: `uv.lock` ~600–900 lines and `pnpm-lock.yaml` ~4,000–6,000 lines. They are generated and should be reviewed as such.

The kickoff's 2-PR split would be ~850 (api+CI) and ~540 (web); both are well over 400. **Recommended: 4 stacked PRs, all labelled M1**. Agents still build in parallel on one tree (§10.1); the lead commits in these slices.

| # | PR | Builders | ~Lines |
| --- | --- | --- | --- |
| 1 | `ci.yml` (api job + disabled deploy-dev), `.gitignore`, `Makefile`, docs stubs, README (api + repo setup + labels), `services/api` skeleton (`pyproject`, settings, `/health`), api tests | infra, backend, qa-evals | ~430 |
| 2 | gateway + fake provider, `evals/` runner + `_smoke`, `packages/rules/schema.json` + README, their tests, `ci.yml` evals step | ai-engineer, rules-curator, qa-evals, infra | ~420 |
| 3 | root `package.json`, `pnpm-workspace.yaml`, `.nvmrc`, `apps/web` scaffold, tokens, fonts, home, loading/error/not-found, Vitest harness, `ci.yml` web job, README web section | frontend, qa-evals, infra | ~300 |
| 4 | App shell: `AppShell`, `SidePanel`, `TopBar`, shell tests | frontend, qa-evals | ~240 |

PR 3 depends only on PR 1 and can be reviewed in parallel with PR 2.

### 10.1 File ownership (non-overlapping; parallel-safe)

| Owner | Files |
| --- | --- |
| infra | `.github/workflows/ci.yml`, `.gitignore`, `Makefile`, `README.md`, `docs/build-plan.md`, `docs/screens.md`, `docs/architecture.md`, GitHub labels |
| backend | `services/api/pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `app/__init__.py`, `app/main.py`, `app/settings.py` |
| ai-engineer | `services/api/app/ai/__init__.py`, `gateway.py`, `fake_provider.py`, `evals/runner.py`, `evals/README.md`, `evals/_smoke/cases.jsonl` |
| rules-curator | `packages/rules/schema.json`, `packages/rules/README.md` |
| frontend | root `package.json`, `pnpm-workspace.yaml`, `pnpm-lock.yaml`, `.nvmrc`, everything in `apps/web/` except qa-evals' files |
| qa-evals | `services/api/tests/**`, `apps/web/tests/**`, `apps/web/vitest.config.ts`, `apps/web/vitest.setup.ts` |

**Shared files and how conflicts are avoided:**
- `services/api/pyproject.toml` (backend):
  - backend adds **all** E0 deps and the tool config up front (§1.2, §1.5), including `jsonschema` for qa and the mypy `files` covering `../../evals`;
  - ai-engineer needs no new deps;
  - anyone needing a change asks backend.
- `apps/web/package.json` (frontend): frontend adds the Vitest/Testing Library/jsdom dev deps and the `test` script up front.
- `ci.yml` (infra): edited sequentially per PR, never in parallel.
- `README.md` (infra, written last): each agent hands infra its "how to run" lines in its handback.
- Root `pnpm-workspace.yaml` and `package.json` (frontend).
- `.gitignore` (infra): others request additions.
- `.claude/settings.json`: no one edits it in E0; security-reviewer reads it.

## 11. Flags

- **needs-founder: yes.**
  - It sets up the merge-to-deploy path.
  - It defines how secrets reach the app (env-only settings, `.env.example`, ignore rules).
  - It adds the gateway, the future spend path.
  - Enabling `deploy-dev` later is a separate needs-founder PR.
- **security-review: yes.** The review covers:
  - GitHub Actions supply chain (SHA pins, `persist-credentials: false`, least-privilege `permissions`);
  - the OIDC/IAM design of the placeholder deploy job;
  - `.gitignore` coverage of env files, local data and large fixtures;
  - `.claude/settings.json`;
  - the chosen dependencies;
  - the gateway's cost log, which must never log prompt text.

  The kickoff's step 3 already requires this.
- `rules-change`: no (schema only, no rules).

## 12. Open questions (Veeru / Nithish)

1. **IaC tool:** Terraform/OpenTofu (recommended: boring, large AWS module ecosystem) or AWS CDK (TypeScript)? It goes in `docs/architecture.md`.
2. **ORM:** confirm SQLAlchemy 2 + Alembic for `docs/architecture.md`.
3. **Node 24 LTS** (recommended) or 22? **pnpm 10**: OK?
4. **Web tests:** OK with Vitest + Testing Library now and Playwright later? **Tailwind v4:** OK?
5. **Test location:** approve `services/api/tests/` + `apps/web/tests/` and amend the CLAUDE.md layout (root `tests/` = e2e + fixtures)?
6. **Web hosting in dev:** a Next.js container on ECS Fargate next to the api (one pipeline), or S3+CloudFront/Amplify? This affects the deploy job.
7. **PR split:** 4 stacked PRs (recommended, each ~≤430) or the kickoff's 2 (~850 + ~540)?
8. **GitHub plan and branch protection.** Which plan (sets the Actions minutes)? Who has admin to create labels and protection? Proposed protection for `main`:
   - require `api` and `web`;
   - 1 approving review (Veeru);
   - dismiss stale reviews;
   - no force-push;
   - linear history.
9. **Dependabot** for Actions SHAs and deps: add in E0 or later?
10. **Jira key** for E0, for the PR template's "Story" field.
11. **Docs content:** who writes `build-plan.md`, `screens.md` and `architecture.md` beyond the stubs, and when? Screen work after E0 is blocked on `screens.md`.
