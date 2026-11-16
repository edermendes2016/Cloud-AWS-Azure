# Azure equivalent of modules/aws/vpc: same three tiers, different building blocks.
#   AWS VPC            -> Virtual Network
#   AWS subnet per AZ  -> one regional subnet per tier (Azure subnets span zones)
#   route to NAT GW    -> NAT gateway associated with the subnet (no route entry needed)
#   security group     -> Network Security Group associated with the subnet
#   VPC flow logs      -> VNet flow logs (Network Watcher), not created here

locals {
  # /16 VNet -> /20 subnets, same layout idea as the AWS module.
  tiers = { public = 0, app = 4, data = 8 }
}

resource "azurerm_virtual_network" "this" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  address_space       = [var.address_space]
  tags                = var.tags
}

resource "azurerm_subnet" "this" {
  for_each = local.tiers

  name                 = "${var.name}-${each.key}"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [cidrsubnet(var.address_space, 4, each.value)]

  # Azure gives every subnet outbound internet by default. Turning that off for the private
  # tiers makes egress explicit: the app tier gets it only through the NAT gateway.
  default_outbound_access_enabled = each.key == "public"
}

resource "azurerm_network_security_group" "this" {
  for_each = local.tiers

  name                = "${var.name}-${each.key}"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = merge(var.tags, { Tier = each.key })
}

# Data tier: the database port is reachable from the app tier only, everything else is denied.
resource "azurerm_network_security_rule" "data_allow_app" {
  name                        = "allow-db-from-app"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.this["data"].name
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = tostring(var.db_port)
  source_address_prefix       = azurerm_subnet.this["app"].address_prefixes[0]
  destination_address_prefix  = "*"
}

resource "azurerm_network_security_rule" "data_deny_rest" {
  name                        = "deny-all-inbound"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.this["data"].name
  priority                    = 4096
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "*"
  destination_address_prefix  = "*"
}

resource "azurerm_subnet_network_security_group_association" "this" {
  for_each = local.tiers

  subnet_id                 = azurerm_subnet.this[each.key].id
  network_security_group_id = azurerm_network_security_group.this[each.key].id
}

# Optional NAT gateway for app tier egress. COST: billed per hour and per GB, like on AWS.
resource "azurerm_public_ip" "nat" {
  count = var.enable_nat_gateway ? 1 : 0

  name                = "${var.name}-nat"
  resource_group_name = var.resource_group_name
  location            = var.location
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.tags
}

resource "azurerm_nat_gateway" "this" {
  count = var.enable_nat_gateway ? 1 : 0

  name                = "${var.name}-nat"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku_name            = "Standard"
  tags                = var.tags
}

resource "azurerm_nat_gateway_public_ip_association" "this" {
  count = var.enable_nat_gateway ? 1 : 0

  nat_gateway_id       = azurerm_nat_gateway.this[0].id
  public_ip_address_id = azurerm_public_ip.nat[0].id
}

resource "azurerm_subnet_nat_gateway_association" "app" {
  count = var.enable_nat_gateway ? 1 : 0

  subnet_id      = azurerm_subnet.this["app"].id
  nat_gateway_id = azurerm_nat_gateway.this[0].id
}
