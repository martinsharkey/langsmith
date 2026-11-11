# Red teaming (gate E2, CTL-05, CTL-06)

All three tools run offline against the platform's own OpenAI-compatible endpoints, so the enclave is tested the
same way as the connected mode (AD-49). Results feed `model-intake evaluate` (per model) and the evidence pack
(per release).

| Tool | Licence | Covers | Config |
| --- | --- | --- | --- |
| garak (NVIDIA) | Apache-2.0 | Prompt injection, jailbreaks, leakage, encoding attacks on a model | `garak/` |
| PyRIT (Microsoft) | MIT | Multi-turn attacks on an agent through its HTTP API (OWASP Agentic ASI01, ASI02, ASI06) | `pyrit/` |
| Inspect (UK AISI) | MIT | AISI-style evaluations and agent tasks in sandboxes, against local vLLM models | `inspect/` |

Mapping to the OWASP LLM Top 10 (2026) and OWASP Agentic Top 10 (2026) is in `owasp-mapping.yaml`. Use the official
OWASP 2026 PDF for numbering (I-14).

These scripts are starting points for delivery stage 4. They have not yet been run against a deployed platform.
