# model-intake

The model intake gate (DP-AI-001-C chapter 6, AD-46). No model is served or routed until this tool has recorded an
approval, and Kyverno refuses any model pod that does not carry the approval's decision ID.

Standard library only (Python 3.10+), so the same tool runs in the connected workspace and inside the enclave.

```
model-intake check    --request request.json --policy policy.json --weights ./weights \
                      --signature manifest.sig --public-key supplier.pub --out ./evidence
model-intake evaluate --policy policy.json --results results.json --out ./evidence
model-intake decide   --check-report ./evidence/check-report.json \
                      --evaluation-report ./evidence/evaluation-report.json \
                      --decision approve --approver "Name" --role SRO --reason "..." --out ./evidence
```

| Step | Checks | Evidence written |
| --- | --- | --- |
| check | request complete; origin and licence on the customer's lists; classification allowed; weights are well-formed safetensors; no pickle or zip payloads anywhere; no symlinks or unknown file types; signature verifies (fails closed) | `manifest.sha256`, `ml-bom.cdx.json` (CycloneDX 1.6), `check-report.json` |
| evaluate | every policy threshold met (garak pass rate, Inspect task scores, customer tests) | `evaluation-report.json` |
| decide | approval only when check and evaluation both passed; approver and role recorded | `decision.json` with ID `INT-YYYYMMDD-xxxxxxxx` |

The signature verifier is set in the policy (`signature_command`). The example uses `cosign verify-blob` over the
manifest with a supplier or site key and no transparency log, which works offline. OpenSSF model signing can be
used instead by changing the command.

Put the evidence directory in the Object Lock evidence bucket (AD-48), then set the decision ID on the model server's
pod annotation `innovox.uk/intake-record`.

Tests: `make test`.
