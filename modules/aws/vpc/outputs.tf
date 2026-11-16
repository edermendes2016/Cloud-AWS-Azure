output "vpc_id" {
  description = "VPC id."
  value       = aws_vpc.this.id
}

output "subnet_ids" {
  description = "Subnet ids grouped by tier (public, app, data)."
  value       = { for tier in keys(local.tiers) : tier => [for k, s in aws_subnet.this : s.id if local.subnets[k].tier == tier] }
}

output "subnet_cidrs" {
  description = "Subnet CIDRs grouped by tier (public, app, data)."
  value       = { for tier in keys(local.tiers) : tier => [for k, s in local.subnets : s.cidr if s.tier == tier] }
}
