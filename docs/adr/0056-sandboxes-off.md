# AD-56 LangSmith sandboxes off in the first build

- Status: Proposed
- Source: DP-AI-001 Solution Architecture v2.0, chapter 14

## Decision

Sandboxes stay disabled. If a client needs agent code execution, they run on a dedicated tainted node pool with a recorded Kyverno exception and their own risk entry.

## Reason

Sandboxes need privileged pods with host networking, /dev/kvm and JuiceFS.
