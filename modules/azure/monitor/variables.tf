variable "name" {
  description = "Name prefix for the workspace, alerts and action group."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that holds the monitoring resources."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "db_server_id" {
  description = "Resource id of the PostgreSQL Flexible Server to monitor."
  type        = string
}

variable "log_retention_days" {
  description = "Log Analytics retention in days. COST: retention above 31 days is billed."
  type        = number
  default     = 30

  validation {
    condition     = var.log_retention_days >= 30 && var.log_retention_days <= 730
    error_message = "Retention must be between 30 and 730 days."
  }
}

variable "cpu_threshold_percent" {
  description = "Average CPU percentage that triggers the alert."
  type        = number
  default     = 80
}

variable "connections_threshold" {
  description = "Average active connections that trigger the alert."
  type        = number
  default     = 80
}

variable "storage_threshold_percent" {
  description = "Used storage percentage that triggers the alert."
  type        = number
  default     = 85
}

variable "alert_emails" {
  description = "E-mail addresses notified by the action group. Empty list creates no action group."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Standard tags applied to every resource."
  type        = map(string)
}
