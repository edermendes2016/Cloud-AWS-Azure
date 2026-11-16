# Lab image: Terraform, the AWS provider and every gate tool, all pinned.
# After the build nothing is downloaded at runtime.
FROM ghcr.io/terraform-linters/tflint:v0.66.0 AS tflint
FROM zricethezav/gitleaks:v8.30.1 AS gitleaks

FROM python:3.13-slim

ARG TERRAFORM_VERSION=1.17.2
ARG AWS_PROVIDER_VERSION=6.20.0
ARG TARGETARCH

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl make unzip \
    && rm -rf /var/lib/apt/lists/*

# Terraform and the provider come from releases.hashicorp.com with checksum verification.
# The provider goes to a filesystem mirror, so `terraform init` never calls the registry.
RUN set -eu; cd /tmp; base=https://releases.hashicorp.com; \
    mirror=/usr/local/share/terraform/plugins/registry.terraform.io/hashicorp/aws; mkdir -p "$mirror"; \
    for item in "terraform ${TERRAFORM_VERSION}" "terraform-provider-aws ${AWS_PROVIDER_VERSION}"; do \
      set -- $item; zip="$1_$2_linux_${TARGETARCH}.zip"; \
      curl -fsSLO "$base/$1/$2/$zip"; \
      curl -fsSL "$base/$1/$2/$1_$2_SHA256SUMS" | grep " $zip\$" | sha256sum -c -; \
    done; \
    unzip -q "terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip" terraform -d /usr/local/bin; \
    mv terraform-provider-aws_*.zip "$mirror/"; rm -f /tmp/*.zip

COPY --from=tflint /usr/local/bin/tflint /usr/local/bin/tflint
COPY --from=gitleaks /usr/bin/gitleaks /usr/local/bin/gitleaks

WORKDIR /lab
COPY requirements.pip .
RUN pip install --no-cache-dir -r requirements.pip

RUN useradd --create-home lab
COPY --chown=lab:lab . .
RUN chown lab:lab /lab
USER lab

# Emulator endpoint and (fake) credentials are set in docker-compose.yml.
ENV IN_LAB=1 \
    AWS_DEFAULT_REGION=us-east-1 \
    TF_IN_AUTOMATION=1 \
    TF_CLI_ARGS=-no-color \
    CHECKPOINT_DISABLE=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s --start-period=20s --retries=40 \
  CMD python -c "import json,urllib.request as u; exit(0 if json.load(u.urlopen('http://localhost:8080/api/status'))['ready'] else 1)"

CMD ["uvicorn", "--app-dir", "app/api", "main:app", "--host", "0.0.0.0", "--port", "8080"]
