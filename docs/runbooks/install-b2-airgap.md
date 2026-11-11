# Install: mode B2 (disconnected enclave)

Same steps as [install-b1.md](install-b1.md), with these differences.

1. **Software arrives only as signed Zarf packages** (`airgap/zarf/README.md`). Verify each package signature with
   the platform cosign public key before deploying it.
2. **RKE2 artefacts and images** are on the carried-in media; `registries.yaml` points at the enclave registry.
3. **Argo CD bootstrap** uses `platform/argocd/root-b2.yaml`; Zarf rewrites the git source to the enclave git server.
4. **LangSmith** needs an offline licence from LangChain (D-06). Insights and Chat stay disabled until their offline
   use is confirmed (`platform/values/langsmith/values-b2.yaml`).
5. **Models**: only weights approved by `model-intake` are carried in; their signatures are verified again inside the
   enclave against the carried-in trust root.
6. **Gate (zero egress)**: run `MODE=b2 tests/run-e2-checks.sh`. Every outbound attempt must fail, and Cilium Hubble
   flow logs must show the drops. Store the output in the evidence bucket.

Known gap (stage 3): Argo CD Helm sources still name upstream chart repositories; the B2 overlay must point them at
the enclave registry's OCI charts before the first enclave sync.
