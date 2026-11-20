# Local equivalents of gate PR. Tools: kubeconform, kyverno, trivy, gitleaks, tofu, yamllint, python3.
SCHEMAS ?= -schema-location default -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'
K8S_VERSION ?= 1.37.2

.PHONY: validate lint secrets schemas policies iac unit tekton airgap zarf-package

validate: lint secrets schemas policies iac unit

lint:
	yamllint -s .
	shellcheck infra/rke2/scripts/*.sh redteam/*/run.sh tests/*.sh e2e/*.sh

secrets:
	gitleaks dir . --config .gitleaks.toml --redact --no-banner

schemas:
	find platform/manifests platform/apps platform/argocd platform/overlays policies/egress policies/kyverno/policies tests/egress infra/rke2/manifests -name '*.yaml' \
	  ! -name kustomization.yaml -print0 | xargs -0 kubeconform -strict -summary \
	  -kubernetes-version $(K8S_VERSION) -skip HelmChartConfig $(SCHEMAS)

policies:
	kyverno test policies/kyverno/tests

iac:
	cd infra/opentofu/nutanix && tofu fmt -check -recursive && tofu init -backend=false -input=false && tofu validate
	trivy config --config trivy.yaml --exit-code 1 .

unit:
	$(MAKE) -C model-intake test

# Tekton Pipelines and Chains from their pinned GitHub release manifests (connected side; mirrored for B2).
tekton:
	kubectl apply -f https://github.com/tektoncd/pipeline/releases/download/v1.18.0/release.yaml
	kubectl apply -f https://github.com/tektoncd/chains/releases/download/v0.30.0/release.yaml
	kubectl apply -f platform/manifests/tekton/chains-config.yaml

# Regenerates the enclave overlay, chart list and Zarf package definitions from platform/apps. Needs helm.
airgap:
	scripts/render_charts.py b2 out/rendered-b2
	scripts/gen_airgap.py --rendered out/rendered-b2

# Connected side: copy the pinned charts into an OCI registry, then build both packages from it.
zarf-package:
	test -n "$(CHART_REGISTRY)" || (echo "set CHART_REGISTRY=<registry[/project]>"; exit 1)
	airgap/push-charts.sh $(CHART_REGISTRY)
	zarf package create airgap/zarf --set CHART_REGISTRY=$(CHART_REGISTRY) --confirm --output out/
	zarf package create airgap/zarf-langsmith --set CHART_REGISTRY=$(CHART_REGISTRY) --confirm --output out/
