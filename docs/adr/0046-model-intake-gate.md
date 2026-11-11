# AD-46 Every model passes the intake gate

- Status: Proposed
- Source: DP-AI-001-C v0.2, chapter 10

## Decision

No model becomes a gateway configuration or a vLLM deployment until `model-intake` records an approval.

## Reason

Model supply chain is a first-order risk; customers bring their own approved lists.
