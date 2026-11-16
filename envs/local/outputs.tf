output "vpc_id" {
  description = "VPC id."
  value       = module.vpc.vpc_id
}

output "db_endpoint" {
  description = "Database endpoint."
  value       = module.rds.endpoint
}

output "db_security_group_id" {
  description = "Database security group id."
  value       = module.rds.security_group_id
}

output "alarm_names" {
  description = "CloudWatch alarm names."
  value       = module.cloudwatch.alarm_names
}
