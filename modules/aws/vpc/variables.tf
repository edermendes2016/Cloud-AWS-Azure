variable "name" {
  description = "Name prefix for every resource of the VPC."
  type        = string
}

variable "cidr_block" {
  description = "VPC CIDR. Must be a /16 so each tier gets /20 subnets."
  type        = string

  validation {
    condition     = can(cidrhost(var.cidr_block, 0)) && endswith(var.cidr_block, "/16")
    error_message = "cidr_block must be a valid /16 CIDR, e.g. 10.20.0.0/16."
  }
}

variable "azs" {
  description = "Availability zones (2 to 4). One subnet per tier is created in each."
  type        = list(string)

  validation {
    condition     = length(var.azs) >= 2 && length(var.azs) <= 4
    error_message = "Provide between 2 and 4 availability zones."
  }
}

variable "enable_nat_gateway" {
  description = "Create NAT gateways so the app tier has outbound internet. COST: billed per hour and per GB."
  type        = bool
  default     = false
}

variable "single_nat_gateway" {
  description = "Use one shared NAT gateway (cheaper, no AZ redundancy) instead of one per AZ."
  type        = bool
  default     = true
}

variable "flow_log_retention_days" {
  description = "Retention of the VPC flow log group, in days."
  type        = number
  default     = 30
}
