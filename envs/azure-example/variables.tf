variable "subscription_id" {
  description = "Azure subscription id (required by the provider to plan or apply)."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "brazilsouth"
}

variable "project" {
  description = "Project tag and name prefix."
  type        = string
  default     = "iac-lab"
}

variable "env" {
  description = "Environment tag and name suffix."
  type        = string
  default     = "example"
}

variable "owner" {
  description = "Owner tag: team accountable for the resources."
  type        = string
  default     = "platform-team"
}

variable "cost_center" {
  description = "CostCenter tag used for cost allocation."
  type        = string
  default     = "lab-0001"
}

variable "address_space" {
  description = "VNet CIDR (/16)."
  type        = string
  default     = "10.30.0.0/16"
}

variable "db_server_id" {
  description = "Resource id of an existing PostgreSQL Flexible Server to monitor."
  type        = string
}
