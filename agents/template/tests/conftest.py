import os

os.environ.setdefault("OIDC_ISSUER", "https://keycloak.test/realms/langsmith")
os.environ.setdefault("OIDC_AUDIENCE", "workbench")
os.environ.setdefault("LANGSMITH_GATEWAY", "http://gateway.test/gateway/v1")
os.environ.setdefault("LANGSMITH_GATEWAY_API_KEY", "test-key")
os.environ.setdefault("LANGSMITH_TRACING", "false")
