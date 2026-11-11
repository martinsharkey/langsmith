# Air-gap packaging (mode B2)

The enclave receives software only as signed Zarf packages carried in on approved media (DP-AI-001-C, Figure 1).

1. On the connected side, `make zarf-images` adds every image the pinned charts reference to the package
   definitions (`zarf dev find-images`), then `make zarf-package` builds the packages and an SBOM for each.
2. Sign each package with the platform cosign key (`zarf package sign`), and record the hashes in the evidence
   bucket.
3. Carry the packages, the cosign public key and the Sigstore trust root into the enclave.
4. In the enclave: `zarf init` (registry and git server), then `zarf package deploy` for each package. Zarf
   rewrites image and git references to the enclave's registry and git server.
5. Argo CD, bootstrapped from `platform/argocd/root-b2.yaml`, syncs the platform from the enclave git server.

Not yet done (stage 3): the B2 overlay that points each Argo CD Helm source at the enclave registry's OCI charts.
Model weights are carried separately, after `model-intake` approval, and never inside these packages.
