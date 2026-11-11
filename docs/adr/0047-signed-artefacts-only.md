# AD-47 Only signed images and model weights are admitted

- Status: Proposed
- Source: DP-AI-001-C v0.2, chapter 10

## Decision

Kyverno verifies cosign signatures at admission; the intake gate verifies model signatures before carry-in.

## Reason

SSDF PS.2 and OWASP Agentic ASI04; prevents substitution.
