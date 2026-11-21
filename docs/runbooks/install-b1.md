# Install: mode B1 (connected, OFFICIAL-SENSITIVE)

Order matters: each step's gate must pass before the next. Commands run from the jump host (the only admin path).
Replace `site.example` hostnames in an overlay for the site; never commit real hostnames to this public repository.

## 0. Prerequisites (delivery stage 1)

- [ ] LangSmith licence (online) from LangChain; open items D-06, I-12 and I-15 answered.
- [ ] Host checks in DP-AI-001-C 5.1: hardened node image, SmithDB cache disks, GPU passthrough.
- [ ] Site DNS names for LangSmith, Harbor and Keycloak; site CA, or accept the platform CA.
- [ ] Approved UK model endpoints from the customer (AD-45).

## 1. Nodes (OpenTofu)

```bash
cd infra/opentofu/nutanix
cp terraform.tfvars.example terraform.tfvars   # set site values; file is git-ignored
export NUTANIX_USERNAME=... NUTANIX_PASSWORD=...   # from the site's credential hand-over
tofu init && tofu plan -out plan && tofu apply plan
```
Label storage nodes `innovox.uk/pool=storage` and GPU nodes with `infra/rke2/config/gpu-agent.yaml`.

## 2. Kubernetes (RKE2, CIS profile)

On each node, with the join token handed over out of band to `/etc/rancher/rke2/token` (mode 0600):
```bash
ROLE=server ARTEFACT_DIR=/opt/rke2-artifacts infra/rke2/scripts/install-rke2-airgap.sh   # first, then other servers
ROLE=agent  ARTEFACT_DIR=/opt/rke2-artifacts infra/rke2/scripts/install-rke2-airgap.sh   # workers
```
Check: `kubectl get nodes` all Ready; Cilium healthy (`kubectl -n kube-system get pods -l k8s-app=cilium`).

## 3. Argo CD and the platform

```bash
git checkout platform-vX.Y.Z   # the release this installation runs; never a branch
helm install argocd argo-cd --repo https://argoproj.github.io/argo-helm --version 10.18.0 -n argocd --create-namespace \
  -f platform/values/argocd/values.yaml
kubectl apply -k platform/argocd/b1
```
The repository and release tag come from one file, `platform/overlays/release/kustomization.yaml`; the root
Application and every child read the same tag. To promote an environment to a new release, check out the new tag
and run `kubectl apply -k platform/argocd/b1` again. A merge to `main` changes no installation.

Argo CD syncs in waves: namespaces and CA (0), operators (1), storage, registry and policies (2), data, identity,
mesh and secrets (3), observability (4), models (5), LangSmith (6). Argo CD waits for each wave's Applications to be
Healthy before it starts the next (Application health check in `platform/values/argocd/values.yaml`).

Argo CD has no local `admin` account. Until Keycloak is up (wave 3), and as break-glass, use the CLI against the
cluster from the jump host: `argocd --core app list`. After wave 3, sign in at `https://argocd.site.example` with a
Keycloak account in group `platform-admins` (full access) or `platform-readonly`.

## 4. Initialise OpenBao (the root app waits here until OpenBao is unsealed and the secrets are written)

OpenBao serves TLS with a certificate from the platform CA (`platform/values/openbao/values.yaml`); the `bao` CLI in
each pod already trusts it. Pods `openbao-1` and `openbao-2` join `openbao-0` over TLS on their own (Raft
`retry_join`), but each pod must be unsealed.
```bash
kubectl -n openbao exec -ti openbao-0 -- bao operator init -key-shares=5 -key-threshold=3
# Hand each unseal key to a named custodian. Never store them in the cluster or in this repository.
for pod in openbao-0 openbao-1 openbao-2; do
  for custodian in 1 2 3; do                                   # threshold 3: three custodians per pod
    kubectl -n openbao exec -ti "$pod" -- bao operator unseal
  done
done
kubectl -n openbao exec -ti openbao-0 -- sh -c '
  bao login && bao secrets enable -path=platform kv-v2 && bao auth enable kubernetes &&
  bao write auth/kubernetes/config kubernetes_host=https://kubernetes.default.svc &&
  bao policy write external-secrets - <<P
path "platform/data/*" { capabilities = ["read"] }
P
  bao write auth/kubernetes/role/external-secrets bound_service_account_names=external-secrets \
    bound_service_account_namespaces=external-secrets policies=external-secrets ttl=1h'
```
Write the platform secrets (generated on the jump host, never echoed to logs). The jump host reaches OpenBao
through a port-forward; its certificate names 127.0.0.1:
```bash
kubectl -n openbao port-forward svc/openbao-active 8200 & pf=$!
sleep 2   # let the port-forward listen
kubectl -n openbao get secret openbao-tls -o jsonpath='{.data.ca\.crt}' | base64 -d > platform-ca.crt
export BAO_ADDR=https://127.0.0.1:8200 BAO_CACERT=$PWD/platform-ca.crt
bao login
bao kv put platform/langsmith/config langsmith_license_key=@licence.txt api_key_salt="$(openssl rand -hex 32)" \
  jwt_secret="$(openssl rand -hex 32)" oauth_client_secret="$(openssl rand -hex 32)" \
  insights_encryption_key="$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')" \
  polly_encryption_key="$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
bao kv put platform/langsmith/postgres langsmith_password="$(openssl rand -hex 24)" smithdb_password="$(openssl rand -hex 24)"
bao kv put platform/langsmith/valkey password="$(openssl rand -hex 24)"
bao kv put platform/harbor/admin password="$(openssl rand -hex 24)"
bao kv put platform/observability/opensearch admin_password="$(openssl rand -hex 24)"
bao kv put platform/observability/grafana admin_user=admin admin_password="$(openssl rand -hex 24)"
bao kv put platform/keycloak/postgres password="$(openssl rand -hex 24)"
bao kv put platform/models/vllm api_key="$(openssl rand -hex 32)"
bao kv put platform/workbench/oidc client_secret="$(openssl rand -hex 32)"   # Keycloak client `workbench`
# Dependency-Track KEK, mode `config`: a base64-encoded 32-byte AES key (chart 2.10.0). It cannot be rotated
# in place, so keep it with the other recovery material.
bao kv put platform/dependency-track/kek kek="$(openssl rand -base64 32)"
```
`tests/config/check_platform.py` fails if an ExternalSecret reads a path or property this step does not write.
After Rook creates the S3 users (wave 2), copy their keys into OpenBao (same shell and port-forward), then stop
the port-forward and remove the CA file:
```bash
k=$(kubectl -n rook-ceph get secret rook-ceph-object-user-platform-langsmith -o jsonpath='{.data.AccessKey}' | base64 -d)
s=$(kubectl -n rook-ceph get secret rook-ceph-object-user-platform-langsmith -o jsonpath='{.data.SecretKey}' | base64 -d)
bao kv put platform/langsmith/s3 access_key="$k" secret_key="$s"
kill "$pf"; rm platform-ca.crt; unset k s
```

## 5. Gate E1

- [ ] Every Argo CD application Synced and Healthy.
- [ ] `kubectl get clusterpolicy` shows all four Kyverno policies Ready; `tests/run-e2-checks.sh` admission checks refuse.
- [ ] LangSmith login through Keycloak with MFA; a trace from a test agent visible in LangSmith (SmithDB).
- [ ] Evidence written to the `evidence` bucket: SBOMs, provenance, admission reports.

## 6. Models

Approve each model with `model-intake` (AD-46), copy the approved weights to the `model-weights` volume, set the
decision ID on `platform/manifests/models/vllm.yaml`, and register the class as an LLM Gateway configuration.
