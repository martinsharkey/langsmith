# LangSmith, self-hosted

LangChain's LangSmith platform, installed exactly as LangChain documents it, so it can be run and tested with its
own features: tracing, evaluation, prompts, and deploying LangGraph agents (Agent Server). Nothing is added
around it.

Source of every step: LangChain's self-hosting guide, <https://docs.langchain.com/langsmith/self-hosted>. If this
page and the guide disagree, follow the guide.

## 1. What you need

- A Kubernetes cluster from a cloud provider (LangChain tests on GKE, EKS, AKS and OpenShift 4.14+). LangChain
  recommends at least 16 vCPUs and 64 GB of memory available, and a storage class backed by SSDs that supports
  volume expansion (`kubectl get storageclass`).
- `kubectl` and `helm` (v3) on your computer, connected to that cluster; `openssl`, and Python with the
  `cryptography` package, to generate secrets.
- A LangSmith licence key from LangChain. Agent Server needs an Enterprise licence.
- Outbound access from the cluster to `https://beacon.langchain.com` (licence check).

To create the cluster, datastores and install together on AWS, Azure or GCP, LangChain also offers
[Deploy with Terraform](https://docs.langchain.com/langsmith/self-host-terraform) instead of the steps below.

## 2. Configure

```bash
cp langsmith_config.example.yaml langsmith_config.yaml     # git ignores langsmith_config.yaml
openssl rand -base64 32                                    # once for apiKeySalt, again for jwtSecret
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # Insights, then Chat
```

Put the values into `langsmith_config.yaml`. Set `apiKeySalt` once and never change it.

## 3. Install

```bash
helm repo add langchain https://langchain-ai.github.io/helm
helm search repo langchain/langsmith --versions            # LangChain recommends the latest version
kubectl create namespace langsmith
helm upgrade -i langsmith langchain/langsmith --values langsmith_config.yaml --version <version> \
  -n langsmith --wait --debug
kubectl get pods -n langsmith
```

By default LangSmith runs its own PostgreSQL, Redis, ClickHouse and blob storage (RustFS) inside the cluster. For
production, LangChain recommends external datastores instead (see the guide).

## 4. Sign in and test

```bash
kubectl get svc -n langsmith                               # the frontend's external IP (LoadBalancer)
curl http://<external ip>/api/tenants
```

Open `http://<external ip>` and sign in with the admin email and password from `langsmith_config.yaml`. Then use
LangSmith as documented: create an API key, send traces from an application, run evaluations.

## 5. Deploy LangGraph agents (Agent Server)

From LangChain's guide, [Enable Agent Server hosting](https://docs.langchain.com/langsmith/enable-self-hosted-agent-server):

1. Install KEDA:
   ```bash
   helm repo add kedacore https://kedacore.github.io/charts
   helm upgrade --install keda kedacore/keda --namespace keda --create-namespace
   ```
2. Give LangSmith a hostname through an ingress, gateway or Istio, and set `config.hostname` in
   `langsmith_config.yaml`.
3. Set `config.deployment.enabled: true` and run the `helm upgrade` command from step 3 again.
4. Build an agent with LangGraph and push its image to a registry the cluster can reach:
   ```bash
   langgraph dev                         # try it locally
   langgraph build -t <registry>/<image>:<tag>
   docker push <registry>/<image>:<tag>
   ```
5. In LangSmith, open **Agent Servers**, choose **+ Agent Server**, and give the image URL.

## Not covered here

Single sign-on, external datastores, ingress and TLS, and air-gapped installs are all in LangChain's guide. Add
them only by following it.
