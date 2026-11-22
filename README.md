# LangSmith, self-hosted

LangChain's LangSmith platform, installed as LangChain documents it, so it can be run and tested with its own
features: tracing, evaluation, prompts, and deploying LangGraph agents (Agent Server). Nothing is added around it.

**LangChain's guide is the source for every step:** <https://docs.langchain.com/langsmith/self-hosted>. This page
gives the short path and the points where a first install goes wrong. Where the two differ, the guide wins, except
for the version notes marked **0.18**, which come from the LangSmith 0.18.1 release itself.

## 1. Before you start

- **Licence:** self-hosted LangSmith is an Enterprise add-on; you need a licence key from LangChain.
- **Cluster:** Kubernetes from your cloud provider (LangChain tests GKE, EKS, AKS and OpenShift 4.14+), with:
  - at least 16 vCPUs and 64 GB of memory available, and one node with at least 4 vCPUs and 16 GB *allocatable*
    for ClickHouse, or its pod never starts;
  - a storage class that creates volumes on demand and supports expansion (`kubectl get storageclass`). On EKS
    that may need the `ebs-csi-driver` add-on;
  - outbound access to `https://beacon.langchain.com` (licence check) and to your model providers.
  See [Kubernetes prerequisites](https://docs.langchain.com/langsmith/kubernetes).
- **Your computer:** `kubectl` and `helm` v3, connected to the cluster; `openssl`; Python with `cryptography`.

## 2. Configure

```bash
cp langsmith_config.example.yaml langsmith_config.yaml     # git ignores it; never commit your real config
openssl rand -base64 32                                    # once for apiKeySalt, again for jwtSecret
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # Insights, then Chat
```

Replace **every** `<...>` value; the chart does not check that `jwtSecret` was changed, and the placeholder is
public. Set `apiKeySalt` once and never change it.

## 3. Install

```bash
helm repo add langchain https://langchain-ai.github.io/helm
helm search repo langchain/langsmith --versions            # LangChain recommends the latest version
kubectl create namespace langsmith
helm upgrade -i langsmith langchain/langsmith --values langsmith_config.yaml --version <version> \
  -n langsmith --wait --debug
kubectl get pods -n langsmith
```

LangSmith runs its own PostgreSQL, Redis, ClickHouse and blob storage inside the cluster. For production LangChain
recommends external datastores (see the guide).

## 4. Sign in and test

The frontend is a `LoadBalancer` service, which a cloud provider may give a **public** IP over plain HTTP. For a
first test, reach it privately instead:

```bash
kubectl port-forward svc/langsmith-frontend 8080:80 -n langsmith
```

Open <http://localhost:8080> and sign in with the admin email and password from your config. Then use LangSmith
as documented: create an API key, send traces, run evaluations. Insights and Chat need model access configured
first ([Insights and Chat](https://docs.langchain.com/langsmith/self-host-insights-chat)).

To open it to others, put it behind an ingress with TLS ([ingress guide](https://docs.langchain.com/langsmith/self-host-ingress)),
or restrict the load balancer with `frontend.service.loadBalancerSourceRanges`.

## 5. Deploy LangGraph agents (Agent Server)

Follow [Enable Agent Server hosting](https://docs.langchain.com/langsmith/enable-self-hosted-agent-server). In short:

1. Install KEDA:
   ```bash
   helm repo add kedacore https://kedacore.github.io/charts
   helm upgrade --install keda kedacore/keda --namespace keda --create-namespace
   ```
2. Install an ingress controller (or Gateway API, or Istio) in the cluster, then uncomment the Agent Server block
   in `langsmith_config.yaml`: `config.hostname`, `config.deployment.enabled`, `ingress.enabled` and
   `frontend.service.type: ClusterIP`. The release refuses to install with Agent Server on and no ingress,
   gateway or Istio gateway enabled. It also refuses `ingress.hostname` and `ingress.subdomain`, even empty
   (moved to `config.hostname` and `config.basePath` in v12), which the ingress guide's example still shows:
   leave them out. Agent Server expects TLS by default (`config.deployment.tlsEnabled: true`): give the ingress
   a certificate as the [ingress guide](https://docs.langchain.com/langsmith/self-host-ingress) describes, or set
   `tlsEnabled: false` for a test without TLS.
3. Run the `helm upgrade` command from step 3 again.
4. Build an agent with LangGraph (needs Docker and the LangGraph CLI) for the cluster's CPU, and push it:
   ```bash
   langgraph dev                                              # try it locally
   langgraph build -t <registry>/<image>:<tag> --platform linux/amd64    # or linux/arm64 for Arm nodes
   docker push <registry>/<image>:<tag>
   ```
   If the registry is private, give the cluster pull access as the guide describes (`operator.templates.deployment`).
5. In LangSmith open **Agent Servers**, choose **+ Agent Server**, and fill in the image URL, Listener/Compute ID
   and namespace ([deploy with the control plane](https://docs.langchain.com/langsmith/deploy-with-control-plane)).

## Defaults to know

- LangSmith sends operational telemetry (logs, metrics, traces) to LangChain unless `config.telemetry` turns it
  off, and usage telemetry unless `PHONE_HOME_USAGE_REPORTING_ENABLED: false` is set in `commonEnv`. The
  licence beacon itself cannot be turned off ([egress](https://docs.langchain.com/langsmith/self-host-egress)).
- Single sign-on, external datastores, TLS and air-gapped installs are in LangChain's guide.
