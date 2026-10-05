"""Eval runner. Run from services/api: `uv run python ../../evals/runner.py --suite <name>`.

Reads evals/<suite>/cases.jsonl, runs each case through the Gateway with FakeProvider,
scores by exact match, writes evals/<suite>/reports/<UTC ts>.json, exits 1 below pass mark.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.ai.fake_provider import FakeProvider
from app.ai.gateway import Gateway, Message, ModelRequest

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_PASS_MARK = 1.0


def load_cases(suite_dir: Path) -> list[dict[str, Any]]:
    lines = (suite_dir / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def resolve_pass_mark(suite_dir: Path, override: float | None) -> float:
    if override is not None:
        return override
    config = suite_dir / "suite.json"
    if config.exists():
        return float(json.loads(config.read_text(encoding="utf-8"))["pass_mark"])
    return DEFAULT_PASS_MARK


def run_suite(suite: str, pass_mark: float | None = None) -> tuple[dict[str, Any], Path]:
    suite_dir = EVALS_DIR / suite
    mark = resolve_pass_mark(suite_dir, pass_mark)
    gateway = Gateway(FakeProvider())
    results: list[dict[str, Any]] = []
    total_cost = Decimal(0)
    for case in load_cases(suite_dir):
        resp = gateway.complete(
            ModelRequest(
                org_id="eval",
                feature=f"eval:{suite}",
                model="fake-echo",
                prompt_id=suite,
                prompt_version="0",
                messages=[Message(role="user", content=str(case["input"]))],
            )
        )
        total_cost += resp.cost_usd
        results.append(
            {
                "id": case["id"],
                "passed": resp.text == case["expected"],
                "cost_usd": str(resp.cost_usd),
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "latency_ms": resp.latency_ms,
            }
        )
    passed = sum(1 for r in results if r["passed"])
    score = passed / len(results) if results else 0.0
    report: dict[str, Any] = {
        "suite": suite,
        "timestamp": datetime.now(UTC).isoformat(),
        "score": score,
        "pass_mark": mark,
        "total_cost_usd": str(total_cost),
        "cases": results,
    }
    reports = suite_dir / "reports"
    reports.mkdir(exist_ok=True)
    path = reports / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report, path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an eval suite.")
    parser.add_argument("--suite", required=True)
    parser.add_argument("--pass-mark", type=float, default=None, help="override suite.json")
    args = parser.parse_args()
    report, path = run_suite(args.suite, args.pass_mark)
    print(f"{'case':<24}{'result':<8}{'cost_usd':>10}")
    for r in report["cases"]:
        print(f"{r['id']:<24}{'pass' if r['passed'] else 'FAIL':<8}{r['cost_usd']:>10}")
    print(
        f"score {report['score']:.2f} / pass mark {report['pass_mark']:.2f}, "
        f"total cost ${report['total_cost_usd']}"
    )
    print(f"report: {path}")
    return 0 if report["score"] >= report["pass_mark"] else 1


if __name__ == "__main__":
    sys.exit(main())
