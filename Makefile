# One entry point for people, CI and the web UI.
# On the host these targets start the containers or forward into the lab container;
# inside the container (IN_LAB=1) they run the real commands.

SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

PIPELINE := fmt validate lint secrets plan scan scan-azure scan-k8s policy cost apply drift destroy orphan-check unlock ci test bootstrap init

ifeq ($(IN_LAB),)

.PHONY: help up down logs $(PIPELINE)

help: ## Show targets
	@echo "make up      start the lab at http://localhost:8080"
	@echo "make test    run the test suite inside the lab"
	@echo "make ci      run every pipeline gate (fmt ... cost)"
	@echo "make down    stop and wipe the lab"
	@echo "pipeline targets: $(PIPELINE)"

up:
	docker compose up -d --build --wait
	@echo "Lab ready: http://localhost:8080"

down:
	docker compose down -v

logs:
	docker compose logs -f lab

$(PIPELINE):
	docker compose exec -T lab make $@ VARS=$(VARS) ID=$(ID)

else

ENV_DIR      := envs/local
TF           := terraform -chdir=$(ENV_DIR)
WORK         := $(or $(LAB_WORK),/tmp/lab)
STATE_BUCKET ?= iac-lab-tfstate
LOCK_TABLE   ?= iac-lab-tflock
BUDGET       ?= 100
# VARS=scenarios/<name>/broken.tfvars plans a failure scenario instead of the baseline
VAR_FILE     := $(if $(VARS),-var-file=$(abspath $(VARS)),)

.PHONY: $(PIPELINE)

bootstrap: ## Create the remote state backend once (S3 + DynamoDB)
	@mkdir -p $(WORK)
	@python scripts/wait_emulator.py $(STATE_BUCKET) || { \
	  terraform -chdir=bootstrap init -input=false >/dev/null; \
	  terraform -chdir=bootstrap apply -input=false -auto-approve -state=$(WORK)/bootstrap.tfstate \
	    -var emulator=true -var enforce_tls=false \
	    -var state_bucket=$(STATE_BUCKET) -var lock_table=$(LOCK_TABLE) \
	    -var 'tags={Project="iac-lab",Env="local",Owner="platform-team",CostCenter="lab-0001",ManagedBy="terraform"}'; }

init: bootstrap ## Initialise the environment against the remote backend
	$(TF) init -input=false -backend-config=backend.local.hcl

fmt: ## Formatting gate
	terraform fmt -check -recursive -diff

validate: ## Syntax and type gate
	terraform -chdir=bootstrap init -input=false -backend=false >/dev/null
	terraform -chdir=bootstrap validate
	$(TF) validate
	terraform -chdir=envs/azure-example init -input=false -backend=false >/dev/null
	terraform -chdir=envs/azure-example validate

lint: ## tflint (bundled terraform ruleset)
	tflint --recursive --config=$(CURDIR)/.tflint.hcl

secrets: ## gitleaks on the working tree
	gitleaks dir . --no-banner --redact

plan: ## Plan and export it as JSON for the gates below
	@mkdir -p $(WORK)
	$(TF) plan -input=false -lock-timeout=0s -out=$(WORK)/tfplan $(VAR_FILE)
	@$(TF) show -json $(WORK)/tfplan > $(WORK)/plan.json

scan: ## Checkov on the resolved plan (built-in checks + policies/checkov)
	checkov -f $(WORK)/plan.json --framework terraform_plan --config-file .checkov.yaml \
	  --repo-root-for-plan-enrichment . --external-checks-dir policies/checkov --quiet --compact --skip-download

scan-azure: ## Checkov on the Azure code (static: there is no Azure account to plan against)
	checkov -d modules/azure -d envs/azure-example --framework terraform --config-file .checkov.yaml \
	  --quiet --compact --skip-download

scan-k8s: ## Checkov on the Kubernetes demonstration manifests (not applied to any cluster)
	checkov -d k8s --framework kubernetes --config-file .checkov.yaml --quiet --compact --skip-download

policy: ## Route and tag rules on the plan
	python scripts/plan_policy.py $(WORK)/plan.json

cost: ## Offline cost estimate with a monthly budget gate
	python scripts/cost_estimate.py $(WORK)/plan.json --budget $(BUDGET)

apply: ## Apply exactly the plan that passed the gates
	$(TF) apply -input=false -lock-timeout=0s $(WORK)/tfplan

drift: ## Fail when real infrastructure differs from the code
	@rc=0; $(TF) plan -input=false -lock-timeout=0s -detailed-exitcode || rc=$$?; \
	if [ $$rc -eq 2 ]; then echo "[FAIL] DRIFT DETECTED: infrastructure differs from the code"; exit 1; fi; \
	if [ $$rc -eq 0 ]; then echo "[PASS] no drift"; fi; exit $$rc

destroy: ## Destroy the environment
	$(TF) destroy -input=false -auto-approve -lock-timeout=0s

orphan-check: ## List anything left outside the Terraform state
	@mkdir -p $(WORK)
	@$(TF) show -json > $(WORK)/state.json
	python scripts/orphan_check.py $(WORK)/state.json

unlock: ## Release a stale state lock: make unlock ID=<lock id>
	$(TF) force-unlock -force $(ID)

ci: fmt validate lint secrets plan scan scan-azure scan-k8s policy cost ## Every gate, in pipeline order

test: ## Unit + integration tests
	python -m pytest -q tests

endif
