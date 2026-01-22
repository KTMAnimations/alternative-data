# Production Environment Configuration
# Deploy with: terraform apply -var-file=environments/production.tfvars
#
# IMPORTANT: Review all values before applying to production!

environment = "production"
aws_region  = "us-east-1"

# VPC Configuration - 3 AZs for high availability
vpc_cidr            = "10.1.0.0/16"
availability_zones  = ["us-east-1a", "us-east-1b", "us-east-1c"]
public_subnet_cidrs = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
private_subnet_cidrs = ["10.1.10.0/24", "10.1.11.0/24", "10.1.12.0/24"]

# RDS Configuration - Multi-AZ for high availability
db_instance_class      = "db.r5.large"
db_allocated_storage   = 100
db_max_storage         = 500
db_multi_az            = true
db_name                = "altdata_production"
db_username            = "altdata_admin"
db_backup_retention    = 30
db_deletion_protection = true
db_performance_insights = true
db_monitoring_interval  = 60

# ElastiCache Configuration - Multi-AZ cluster
redis_node_type          = "cache.r5.large"
redis_num_cache_nodes    = 2
redis_engine_version     = "7.0"
redis_automatic_failover = true
redis_multi_az           = true

# ECS Configuration - Higher capacity
ecs_cpu           = 1024
ecs_memory        = 2048
ecs_desired_count = 4
ecs_min_capacity  = 2
ecs_max_capacity  = 10
container_port    = 8000
health_check_path = "/health"

# Auto-scaling thresholds
autoscaling_cpu_target         = 70
autoscaling_memory_target      = 80
autoscaling_scale_in_cooldown  = 300
autoscaling_scale_out_cooldown = 60

# ALB Configuration
alb_internal              = false
alb_idle_timeout          = 120
alb_health_check_interval = 15
alb_healthy_threshold     = 2
alb_unhealthy_threshold   = 2

# S3 Configuration - With replication
s3_versioning_enabled      = true
s3_lifecycle_enabled       = true
s3_transition_days         = 30
s3_glacier_transition_days = 90
s3_expiration_days         = 365
s3_replication_enabled     = true
s3_replication_region      = "us-west-2"

# CloudWatch Configuration
log_retention_days       = 90
alarm_evaluation_periods = 2
alarm_period             = 60

# Alarms
enable_alarms           = true
alarm_cpu_threshold     = 80
alarm_memory_threshold  = 85
alarm_error_threshold   = 10
alarm_latency_threshold = 1000

# API Configuration
api_rate_limit  = 10000
api_burst_limit = 20000

# Domain Configuration (uncomment and set for production)
# domain_name     = "api.altdata.example.com"
# certificate_arn = "arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/xxx"

# WAF Configuration
enable_waf     = true
waf_rate_limit = 2000

# Secrets Manager
secrets_rotation_days = 30

# Tags
tags = {
  Environment = "production"
  Project     = "altdata-platform"
  ManagedBy   = "terraform"
  CostCenter  = "engineering"
  Compliance  = "sox"
  DataClass   = "confidential"
}
