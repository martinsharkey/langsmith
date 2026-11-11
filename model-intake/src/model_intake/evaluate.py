"""Compare evaluation results (Inspect, garak, task tests) with the policy's minimum scores."""

from __future__ import annotations

from .policy import EvaluationThreshold


def check_thresholds(results: dict, thresholds: list[EvaluationThreshold]) -> tuple[bool, list[dict]]:
    """results: {"<evaluation name>": {"<metric>": value, ...}, ...}. Every threshold must be met."""
    outcome = []
    passed = True
    for t in thresholds:
        value = results.get(t.name, {}).get(t.metric)
        if value is None:
            outcome.append({"evaluation": t.name, "metric": t.metric, "minimum": t.minimum, "value": None,
                            "passed": False, "detail": "result missing"})
            passed = False
            continue
        ok = float(value) >= t.minimum
        passed = passed and ok
        outcome.append({"evaluation": t.name, "metric": t.metric, "minimum": t.minimum, "value": float(value),
                        "passed": ok})
    return passed, outcome
