# Private PostgreSQL instance: data-tier subnets only, encrypted, no public access,
# master password generated and stored by Secrets Manager (never in code or state).

locals {
  default_parameters = {
    "log_connections" = "1"
    "rds.force_ssl"   = "1"
  }
}

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
}

# Inline rules on purpose: Terraform owns the full rule set, so a rule opened by hand
# in the console is reported as drift and removed by the next apply.
resource "aws_security_group" "this" {
  name        = "${var.name}-db"
  description = "Database access for ${var.name}"
  vpc_id      = var.vpc_id

  ingress {
    description = "PostgreSQL from allowed networks only"
    from_port   = var.port
    to_port     = var.port
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  tags = { Name = "${var.name}-db" }
}

resource "aws_db_parameter_group" "this" {
  name   = var.name
  family = "postgres${split(".", var.engine_version)[0]}"

  dynamic "parameter" {
    for_each = coalesce(var.parameters, local.default_parameters)

    content {
      name  = parameter.key
      value = parameter.value
    }
  }
}

resource "aws_db_instance" "this" {
  identifier     = var.name
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class
  db_name        = var.db_name
  port           = var.port

  allocated_storage = var.allocated_storage_gb
  storage_type      = "gp3"
  storage_encrypted = true

  username                            = var.master_username
  manage_master_user_password         = true
  iam_database_authentication_enabled = true
  ca_cert_identifier                  = "rds-ca-rsa2048-g1"
  performance_insights_enabled        = var.performance_insights_enabled

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.this.id]
  parameter_group_name   = aws_db_parameter_group.this.name
  publicly_accessible    = false
  multi_az               = var.multi_az

  backup_retention_period         = var.backup_retention_days
  copy_tags_to_snapshot           = true
  auto_minor_version_upgrade      = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  deletion_protection             = var.deletion_protection
  skip_final_snapshot             = var.skip_final_snapshot
  final_snapshot_identifier       = var.skip_final_snapshot ? null : "${var.name}-final"
}
