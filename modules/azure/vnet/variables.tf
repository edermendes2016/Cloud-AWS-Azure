variable "name" {
  description = "Name prefix for every resource of the virtual network."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that holds the network."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "address_space" {
  description = "VNet CIDR. Must be a /16 so each tier gets a /20 subnet."
  type        = string

  validation {
    condition     = can(cidrhost(var.address_space, 0)) && endswith(var.address_space, "/16")
    error_message = "address_space must be a valid /16 CIDR, e.g. 10.30.0.0/16."
  }
}

variable "db_port" {
  description = "Database port opened from the app tier to the data tier."
  type        = number
  default     = 5432
}

variable "enable_nat_gateway" {
  description = "Create a NAT gateway for app tier egress. COST: billed per hour and per GB."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Standard tags applied to every resource."
  type        = map(string)
}
