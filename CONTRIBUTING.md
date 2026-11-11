# Contributing

Work follows the secure lifecycle in [docs/sdlc.md](docs/sdlc.md).

1. Branch from `main`; one change per pull request.
2. Run `make validate` before you push.
3. Every pull request passes gate **PR**: lint, render, schema validation, policy tests, unit tests, IaC scan,
   secret scan. Branch protection requires one reviewer who is not the author.
4. A change to security policy (`policies/`), the intake gate (`model-intake/`) or pinned versions
   (`versions.yaml`) also needs review from the security owner in `.github/CODEOWNERS`.
5. Never rebuild or patch a vendor image or chart (AD-40). Configure it through documented values instead.
6. Only OSI-approved open-source components may be added (AD-52). Source-available licences such as the Business
   Source Licence are refused.
