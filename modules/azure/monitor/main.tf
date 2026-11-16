# Azure equivalent of modules/aws/cloudwatch for a PostgreSQL Flexible Server.
#   CloudWatch log group -> Log Analytics workspace
#   CloudWatch alarm     -> Azure Monitor metric alert
#   SNS topic            -> action group

locals {
  alerts = {
    cpu-high = {
      metric    = "cpu_percent"
      operator  = "GreaterThan"
      threshold = var.cpu_threshold_percent
      text      = "CPU above ${var.cpu_threshold_percent}% for 10 minutes"
    }
    connections-high = {
      metric    = "active_connections"
      operator  = "GreaterThan"
      threshold = var.connections_threshold
      text      = "More than ${var.connections_threshold} active connections for 10 minutes"
    }
    storage-high = {
      metric    = "storage_percent"
      operator  = "GreaterThan"
      threshold = var.storage_threshold_percent
      text      = "Storage above ${var.storage_threshold_percent}% used"
    }
  }
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  tags                = var.tags
}

resource "azurerm_monitor_action_group" "alerts" {
  count = length(var.alert_emails) > 0 ? 1 : 0

  name                = "${var.name}-alerts"
  resource_group_name = var.resource_group_name
  short_name          = "alerts"
  tags                = var.tags

  dynamic "email_receiver" {
    for_each = var.alert_emails

    content {
      name          = "email-${email_receiver.key}"
      email_address = email_receiver.value
    }
  }
}

resource "azurerm_monitor_metric_alert" "db" {
  for_each = local.alerts

  name                = "${var.name}-db-${each.key}"
  resource_group_name = var.resource_group_name
  scopes              = [var.db_server_id]
  description         = each.value.text
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  tags                = var.tags

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = each.value.metric
    aggregation      = "Average"
    operator         = each.value.operator
    threshold        = each.value.threshold
  }

  dynamic "action" {
    for_each = azurerm_monitor_action_group.alerts

    content {
      action_group_id = action.value.id
    }
  }
}
