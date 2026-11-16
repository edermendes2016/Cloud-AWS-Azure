output "workspace_id" {
  description = "Log Analytics workspace id."
  value       = azurerm_log_analytics_workspace.this.id
}

output "alert_names" {
  description = "Names of the database metric alerts."
  value       = [for a in azurerm_monitor_metric_alert.db : a.name]
}
