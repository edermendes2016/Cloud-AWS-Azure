# Reference wiring of the Azure modules. There is no Azure emulator and no Azure account
# behind this lab, so this environment is checked with `terraform validate` and Checkov only.
# It has never been planned or applied.

provider "azurerm" {
  features {}

  subscription_id = var.subscription_id
}

locals {
  name = "${var.project}-${var.env}"

  tags = {
    Project    = var.project
    Env        = var.env
    Owner      = var.owner
    CostCenter = var.cost_center
    ManagedBy  = "terraform"
  }
}

resource "azurerm_resource_group" "this" {
  name     = local.name
  location = var.location
  tags     = local.tags
}

module "vnet" {
  source = "../../modules/azure/vnet"

  name                = local.name
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  address_space       = var.address_space
  enable_nat_gateway  = true
  tags                = local.tags
}

module "monitor" {
  source = "../../modules/azure/monitor"

  name                = local.name
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  db_server_id        = var.db_server_id
  tags                = local.tags
}
