variable "name" {
  description = "Name prefix for log group, alarms and dashboard."
  type        = string
}

variable "region" {
  description = "Region shown by the dashboard widgets."
  type        = string
}

variable "db_instance_id" {
  description = "RDS instance identifier to monitor."
  type        = string
}

variable "log_retention_days" {
  description = "Retention of the application log group. COST: logs without retention grow forever."
  type        = number
  default     = 30
}

variable "cpu_threshold_percent" {
  description = "Average CPU percentage that triggers the alarm."
  type        = number
  default     = 80

  validation {
    condition     = var.cpu_threshold_percent > 0 && var.cpu_threshold_percent <= 100
    error_message = "CPU threshold must be between 1 and 100."
  }
}

variable "connections_threshold" {
  description = "Average open connections that trigger the alarm."
  type        = number
  default     = 80
}

variable "free_storage_threshold_gb" {
  description = "Free storage in GB below which the alarm triggers."
  type        = number
  default     = 5
}

variable "create_sns_topic" {
  description = "Create an SNS topic and send alarm state changes to it."
  type        = bool
  default     = false
}
