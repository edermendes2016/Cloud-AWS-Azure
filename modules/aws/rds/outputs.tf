output "instance_id" {
  description = "DB instance identifier (CloudWatch dimension)."
  value       = aws_db_instance.this.identifier
}

output "endpoint" {
  description = "Connection endpoint."
  value       = aws_db_instance.this.endpoint
}

output "security_group_id" {
  description = "Security group that guards the database."
  value       = aws_security_group.this.id
}

output "master_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the master password."
  value       = try(aws_db_instance.this.master_user_secret[0].secret_arn, null)
}
