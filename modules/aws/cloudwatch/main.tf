# Observability for one RDS instance: app log group, three alarms and a dashboard.

locals {
  alarms = {
    cpu-high = {
      metric     = "CPUUtilization"
      comparison = "GreaterThanThreshold"
      threshold  = var.cpu_threshold_percent
      text       = "CPU above ${var.cpu_threshold_percent}% for 10 minutes"
    }
    connections-high = {
      metric     = "DatabaseConnections"
      comparison = "GreaterThanThreshold"
      threshold  = var.connections_threshold
      text       = "More than ${var.connections_threshold} open connections for 10 minutes"
    }
    storage-low = {
      metric     = "FreeStorageSpace"
      comparison = "LessThanThreshold"
      threshold  = var.free_storage_threshold_gb * 1024 * 1024 * 1024
      text       = "Less than ${var.free_storage_threshold_gb} GB of free storage"
    }
  }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/app/${var.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_sns_topic" "alerts" {
  count = var.create_sns_topic ? 1 : 0

  name              = "${var.name}-alerts"
  kms_master_key_id = "alias/aws/sns"
}

resource "aws_cloudwatch_metric_alarm" "rds" {
  for_each = local.alarms

  alarm_name          = "${var.name}-rds-${each.key}"
  alarm_description   = each.value.text
  namespace           = "AWS/RDS"
  metric_name         = each.value.metric
  dimensions          = { DBInstanceIdentifier = var.db_instance_id }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  comparison_operator = each.value.comparison
  threshold           = each.value.threshold
  treat_missing_data  = "missing"
  alarm_actions       = aws_sns_topic.alerts[*].arn
  ok_actions          = aws_sns_topic.alerts[*].arn
}

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = var.name

  dashboard_body = jsonencode({
    widgets = [
      for i, key in keys(local.alarms) : {
        type   = "metric"
        x      = i * 8
        y      = 0
        width  = 8
        height = 6
        properties = {
          title   = local.alarms[key].metric
          region  = var.region
          stat    = "Average"
          period  = 300
          metrics = [["AWS/RDS", local.alarms[key].metric, "DBInstanceIdentifier", var.db_instance_id]]
        }
      }
    ]
  })
}
