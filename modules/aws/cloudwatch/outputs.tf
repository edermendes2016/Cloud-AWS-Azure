output "alarm_names" {
  description = "Names of the RDS alarms."
  value       = [for a in aws_cloudwatch_metric_alarm.rds : a.alarm_name]
}

output "log_group_name" {
  description = "Application log group."
  value       = aws_cloudwatch_log_group.app.name
}

output "sns_topic_arn" {
  description = "Alerts topic ARN, when created."
  value       = one(aws_sns_topic.alerts[*].arn)
}
