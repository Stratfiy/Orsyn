# Evals

Prompts are code and evals are tests. Every agent change ships with its eval cases and a passing report.

## Run

From `services/api`:

```
uv run python ../../evals/runner.py --suite _smoke
```

Exit code is 0 at or above the pass mark, 1 below it (this blocks the PR). Until real providers exist the runner uses `FakeProvider` through the `Gateway`, so no network and no cost.

## Layout per agent

```
evals/<agent>/
  cases.jsonl     one JSON object per line: {"id", "input", "expected"}
  suite.json      optional: {"pass_mark": 0.8}; default 1.0
  reports/        <UTC timestamp>.json (gitignored)
```

`--pass-mark X` overrides `suite.json` for a single run. Scoring is exact match on the model text.

## Pass marks (from CLAUDE.md)

- Code suggestions (HSN/SAC): 0.80 right with no edits.
- RFQ from a drawing: 0.90 on material, dimensions, quantity, tolerances, standards.
- Quote drafts: sendable with two edits or fewer.
- Export roadmap: zero wrong mandatory steps (1.0).
- `_smoke`: 1.0.

## Report

`reports/<ts>.json` holds `score`, `pass_mark`, `total_cost_usd` and, per case, `passed`, `cost_usd`, tokens and `latency_ms`. AI cost per case is always reported.
