# Kickoff prompt — paste into the first Claude Code session

Read `CLAUDE.md` and every file in `.claude/agents/`. You lead this team: delegate to the subagents exactly as "How a story flows" in CLAUDE.md says, and don't do their work yourself.

**Story for this session: E0 "Repo, CI and environments".**
Done when: every PR runs tests; merges deploy to dev automatically. The AWS account doesn't exist yet, so build CI now and leave the deploy job as a documented, disabled placeholder.

1. **architect** writes `docs/plans/E0-repo-ci.md`: the monorepo layout in CLAUDE.md, tooling (uv for Python, pnpm for web), lint, type-check and test commands, the CI workflow, labels and the docs skeleton. Then stop and show me the plan. Wait for my OK.
2. After my OK:
   - **infra:** `.github/workflows/ci.yml` running lint, type-check and tests for api and web on every PR; the disabled deploy-to-dev job.
   - **backend:** `services/api` FastAPI app with a `/health` endpoint, settings from environment variables, pytest, ruff and mypy.
   - **frontend:** `apps/web` Next.js 15 with Tailwind, the design tokens and fonts from `.claude/agents/frontend.md`, the app shell (rounded collapsible side panel, rounded top bar, light theme) and a placeholder home page.
   - **ai-engineer:** `services/api/app/ai/gateway.py` interface with a fake provider and cost logging, plus an `evals/` runner skeleton. No real model calls.
   - **rules-curator:** `packages/rules/schema.json` and a README describing the rule shape. No rules yet.
   - **qa-evals:** the test harness for api and web, wired into CI.
3. **security-reviewer** checks CI, `.claude/settings.json`, `.gitignore` (env files, local data, large fixtures) and the dependencies chosen.
4. **product-reviewer** checks the "Done when".
5. Open one PR labelled M1, using `.github/pull_request_template.md`. If it goes past about 400 changed lines, split it in two: api with CI, then web.

Rules for this session: no feature code, no real model calls, no secrets in the repo. Update `README.md` with how to run api and web locally and how to run tests.

Finish with a short summary: what's in, the commands, which model each subagent actually ran on, and what Veeru must still do (branch protection, AWS account, environment variables).
