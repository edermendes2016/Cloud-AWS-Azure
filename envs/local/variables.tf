variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "emulator" {
  description = "True when the target is a local emulator (relaxes credential checks only)."
  type        = bool
  default     = true
}

variable "project" {
  description = "Project tag and name prefix."
  type        = string
  default     = "iac-lab"
}

variable "env" {
  description = "Environment tag and name suffix."
  type        = string
  default     = "local"
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

variable "vpc_cidr" {
  description = "VPC CIDR (/16)."
  type        = string
  default     = "10.20.0.0/16"
}

variable "azs" {
  description = "Availability zones."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "enable_nat_gateway" {
  description = "NAT gateway for app tier egress. The route policy requires it."
  type        = bool
  default     = true
}

variable "db_allowed_cidr_blocks" {
  description = "Networks allowed on the database port. Null means the app tier subnets."
  type        = list(string)
  default     = null
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t3.micro"
}

variable "db_multi_az" {
  description = "RDS Multi-AZ."
  type        = bool
  default     = false
}
