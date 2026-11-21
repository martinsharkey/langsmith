# AD-66 Every Innovox image is signed with the platform key; releases promote the tested digest

- Status: Accepted
- Source: owner ruling on issue 37, 2026-11-21: "Platform key". Every Innovox image is signed with the platform
  key (B1 and B2); keyless signing is kept for provenance only; CI promotes the exact digest the PR gate tested.

## Decision

- Admission (`policies/kyverno/policies/verify-innovox-signatures.yaml`) trusts one attestor for Innovox images:
  the platform cosign key, verified offline with no transparency log, in both modes. It verifies every image a pod
  runs or mounts: containers, init containers, ephemeral containers and image volumes (model weights).
- Every Innovox image is signed with that key. In GitHub Actions the agent release lane
  (`.github/workflows/agent-release.yml`) signs with it; on a platform, Tekton Chains signs with the same key from
  Secret `tekton-chains/signing-secrets` (`platform/manifests/tekton`). SBOMs are attested with the same key.
- A keyless signature with the release workflow's identity is added for provenance only. Admission does not accept
  it and does not depend on Rekor or Fulcio.
- A release never rebuilds. Gate PR, on push to `main`, publishes the image it built, scanned and evaluated as
  `agent-template:sha-<commit>` and records its digest. A release tag on that commit promotes that digest: the
  release job refuses a commit on which gate PR has not passed on push to `main`, and refuses any ref that is not
  a release tag (also when dispatched by hand).
- The release job then runs the admission policy itself against the released digest, with the platform public key
  (`scripts/verify_signatures.py`), so "signed" means "admission would accept it".

## Reason

The key-based attestor works offline in the enclave and is the one admission enforces, so one signature serves B1
and B2. A digest promoted from the tested build removes the gap between what was tested and what is released.

## Consequences

- The platform private key is held in OpenBao for Tekton Chains and in the GitHub environment `agent-release`
  (secrets `PLATFORM_COSIGN_KEY`, `PLATFORM_COSIGN_PASSWORD`; variable `PLATFORM_COSIGN_PUBLIC_KEY`). Its rotation
  must update Secret `kyverno/cosign-public-key` in the same change.
- Images copied into Harbor must be copied with their signatures (for example `cosign copy`, or a Zarf package).
