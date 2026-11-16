variable "name" {
  description = "Identifier of the instance and prefix of related resources."
  type        = string
}

variable "vpc_id" {
  description = "VPC where the database security group is created."
  type        = string
}

variable "subnet_ids" {
  description = "Private (data tier) subnets for the DB subnet group. At least two AZs."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "A DB subnet group needs subnets in at least two availability zones."
  }
}

variable "allowed_cidr_blocks" {
  description = "Networks allowed to reach the database port (least privilege: the app tier only)."
  type        = list(string)
}

variable "engine_version" {
  description = "PostgreSQL engine version."
  type        = string
  default     = "16.3"
}

variable "instance_class" {
  description = "Instance class. COST: main driver of the monthly bill."
  type        = string
  default     = "db.t3.micro"
}

variable "allocated_storage_gb" {
  description = "Allocated gp3 storage in GB."
  type        = number
  default     = 20

  validation {
    condition     = var.allocated_storage_gb >= 20
    error_message = "gp3 storage for PostgreSQL starts at 20 GB."
  }
}

variable "multi_az" {
  description = "Standby replica in another AZ. COST: doubles the instance price."
  type        = bool
  default     = false
}

variable "db_name" {
  description = "Initial database name."
  type        = string
  default     = "app"
}

variable "master_username" {
  description = "Master user name. The password is managed by Secrets Manager."
  type        = string
  default     = "dbadmin"
}

variable "parameters" {
  description = "Parameter group settings. Null applies the defaults: force TLS and log every connection."
  type        = map(string)
  default     = null
}

variable "performance_insights_enabled" {
  description = "Enable Performance Insights (7 days of history are free)."
  type        = bool
  default     = true
}

variable "port" {
  description = "Database port."
  type        = number
  default     = 5432
}

variable "backup_retention_days" {
  description = "Automated backup retention in days."
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35
    error_message = "Backup retention must be between 1 and 35 days."
  }
}

variable "deletion_protection" {
  description = "Block accidental deletion. Keep true in production."
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Skip the final snapshot on destroy. Only for disposable environments."
  type        = bool
  default     = false
}
