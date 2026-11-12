# AD-53 LangChain's documented recommendation takes precedence

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.0, chapter 14

## Decision

Where LangChain documents a recommended technology or configuration, the platform uses it. Open-source components fill only the gaps; where a recommendation assumes a managed cloud service, the open-source equivalent is used and the gap is recorded as a risk.

## Reason

Vendor-native use keeps every LangSmith release upgradeable and supportable.
