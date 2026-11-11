"""Customer intake policy and model request, loaded from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_REQUEST_FIELDS = (
    "model_name",
    "model_version",
    "supplier",
    "origin_country",
    "licence",
    "source",
    "intended_use",
    "classification",
)


@dataclass
class EvaluationThreshold:
    name: str
    metric: str
    minimum: float


@dataclass
class Policy:
    allowed_origins: list[str]
    allowed_licences: list[str]
    weight_extensions: list[str] = field(default_factory=lambda: [".safetensors"])
    allowed_aux_extensions: list[str] = field(default_factory=list)
    forbidden_extensions: list[str] = field(default_factory=list)
    allowed_classifications: list[str] = field(default_factory=lambda: ["OFFICIAL", "OFFICIAL-SENSITIVE"])
    signature_command: list[str] = field(default_factory=list)
    evaluations: list[EvaluationThreshold] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Policy":
        evals = [EvaluationThreshold(e["name"], e["metric"], float(e["minimum"])) for e in data.get("evaluations", [])]
        return cls(
            allowed_origins=[c.upper() for c in data["allowed_origins"]],
            allowed_licences=list(data["allowed_licences"]),
            weight_extensions=[e.lower() for e in data.get("weight_extensions", [".safetensors"])],
            allowed_aux_extensions=[e.lower() for e in data.get("allowed_aux_extensions", [])],
            forbidden_extensions=[e.lower() for e in data.get("forbidden_extensions", [])],
            allowed_classifications=list(data.get("allowed_classifications", ["OFFICIAL", "OFFICIAL-SENSITIVE"])),
            signature_command=list(data.get("signature_command", [])),
            evaluations=evals,
        )


def load_json(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_policy(path: str | Path) -> Policy:
    return Policy.from_dict(load_json(path))


def validate_request(request: dict) -> list[str]:
    """Return the problems with a model request; empty when it is complete."""
    problems = [f"request is missing '{f}'" for f in REQUIRED_REQUEST_FIELDS if not str(request.get(f, "")).strip()]
    country = str(request.get("origin_country", ""))
    if country and (len(country) != 2 or not country.isalpha()):
        problems.append("origin_country must be an ISO 3166-1 alpha-2 code, for example GB")
    return problems
