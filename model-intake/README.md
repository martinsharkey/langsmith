# model-intake

The model intake gate (DP-AI-001-C chapter 6, AD-46). No model is served or routed until this tool has recorded an
approval, and Kyverno refuses any model pod that does not carry the approval's decision ID.

Standard library only (Python 3.10+), so the same tool runs in the connected workspace and inside the enclave.

```
model-intake check    --request request.json --policy policy.json --weights ./weights \
                      --signature manifest.sig --public-key supplier.pub --out ./evidence
model-intake evaluate --policy policy.json --results results.json \
                      --check-report ./evidence/check-report.json --out ./evidence
model-intake decide   --check-report ./evidence/check-report.json \
                      --evaluation-report ./evidence/evaluation-report.json \
                      --weights-image <registry>/innovox/models/<name>@sha256:<digest> \
                      --decision approve --approver "Name" --role SRO --reason "..." --out ./evidence
```

| Step | Checks | Evidence written |
| --- | --- | --- |
| check | request complete; origin and licence on the customer's lists; classification allowed; weights are well-formed safetensors; no pickle or zip payloads anywhere; no symbolic links (to files or directories), special files or unknown file types; signature verifies (fails closed) | `manifest.sha256`, `ml-bom.cdx.json` (CycloneDX 1.6), `check-report.json` |
| evaluate | every policy threshold met (garak pass rate, Inspect task scores, customer tests); the report names the model, version and weights manifest it is about | `evaluation-report.json` |
| decide | approval only when check and evaluation both passed and the evaluation is of the same model and weights; the weights image must be named by digest; approver and role recorded | `decision.json` with ID `INT-YYYYMMDD-xxxxxxxx` and the admission entry |

The signature verifier is set in the policy (`signature_command`). The example uses `cosign verify-blob` over the
manifest with a supplier or site key and no transparency log, which works offline. OpenSSF model signing can be
used instead by changing the command.

The weights are served as a signed OCI image mounted as an image volume (owner ruling on issue 49), so the approval
names that image by digest. Put the evidence directory in the Object Lock evidence bucket (AD-48), add the entry that
`decide` prints (`<decision ID>: <weights image>`) to `policies/kyverno/policies/model-intake-decisions.yaml`
through a reviewed pull request, then set the decision ID on the model server's pod annotation
`innovox.uk/intake-record` and the same image as its weights volume. Admission refuses a model pod whose ID is not in
that list or whose image volume is not the approved image (require-model-intake-record).

Tests: `make test`.
