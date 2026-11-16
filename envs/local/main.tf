# Reference environment. Targets the local emulator by default (see backend.local.hcl and
# the AWS_ENDPOINT_URL variable); the same code plans against a real account with emulator=false.

terraform {
  backend "s3" {}
}

provider "aws" {
  region                      = var.region
  s3_use_path_style           = var.emulator
  skip_credentials_validation = var.emulator
  skip_metadata_api_check     = var.emulator
  skip_requesting_account_id  = var.emulator

  default_tags {
    tags = {
      Project    = var.project
      Env        = var.env
      Owner      = var.owner
      CostCenter = var.cost_center
      ManagedBy  = "terraform"
    }
  }
}

locals {
  name = "${var.project}-${var.env}"
}

module "vpc" {
  source = "../../modules/aws/vpc"

  name               = local.name
  cidr_block         = var.vpc_cidr
  azs                = var.azs
  enable_nat_gateway = var.enable_nat_gateway
}

module "rds" {
  source = "../../modules/aws/rds"

  name                = local.name
  vpc_id              = module.vpc.vpc_id
  subnet_ids          = module.vpc.subnet_ids["data"]
  allowed_cidr_blocks = coalesce(var.db_allowed_cidr_blocks, module.vpc.subnet_cidrs["app"])
  instance_class      = var.db_instance_class
  multi_az            = var.db_multi_az

  # The emulator does not keep parameter values or Performance Insights, which would show
  # as permanent drift. Against a real account the module defaults (both on) apply.
  parameters                   = var.emulator ? {} : null
  performance_insights_enabled = !var.emulator

  # Disposable lab environment: must be destroyable in one run.
  deletion_protection = false
  skip_final_snapshot = true
}

module "cloudwatch" {
  source = "../../modules/aws/cloudwatch"

  name           = local.name
  region         = var.region
  db_instance_id = module.rds.instance_id
}
