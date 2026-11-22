# Security policy

Report a vulnerability privately through GitHub's
[private vulnerability reporting](../../security/advisories/new) for this repository, not in a public issue.

Never commit secrets: the LangSmith licence key, `apiKeySalt`, `jwtSecret`, encryption keys or passwords. They
belong only in your own `langsmith_config.yaml`, which git ignores.
