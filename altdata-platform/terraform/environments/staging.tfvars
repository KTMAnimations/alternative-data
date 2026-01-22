# Staging Environment Configuration
# Deploy with: terraform apply -var-file=environments/staging.tfvars

environment = "staging"
aws_region  = "us-east-1"

# VPC Configuration
vpc_cidr            = "10.0.0.0/16"
availability_zones  = ["us-east-1a", "us-east-1b"]
public_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]

# RDS Configuration
db_instance_class    = "db.t3.medium"
db_allocated_storage = 20
db_max_storage       = 100
db_multi_az          = false
db_name              = "altdata_staging"
db_username          = "altdata_admin"
db_backup_retention  = 7
db_deletion_protection = false

# ElastiCache Configuration
redis_node_type       = "cache.t3.micro"
redis_num_cache_nodes = 1
redis_engine_version  = "7.0"

# ECS Configuration
ecs_cpu           = 512
ecs_memory        = 1024
ecs_desired_count = 2
ecs_min_capacity  = 1
ecs_max_capacity  = 4
container_port    = 8000
health_check_path = "/health"

# Auto-scaling thresholds
autoscaling_cpu_target    = 70
autoscaling_memory_target = 80

# ALB Configuration
alb_internal              = false
alb_idle_timeout          = 60
alb_health_check_interval = 30
alb_healthy_threshold     = 2
alb_unhealthy_threshold   = 3

# S3 Configuration
s3_versioning_enabled = true
s3_lifecycle_enabled  = true
s3_transition_days    = 30
s3_expiration_days    = 90

# CloudWatch Configuration
log_retention_days       = 14
alarm_evaluation_periods = 2
alarm_period             = 300

# API Configuration
api_rate_limit  = 1000
api_burst_limit = 2000

# Tags
tags = {
  Environment = "staging"
  Project     = "altdata-platform"
  ManagedBy   = "terraform"
  CostCenter  = "engineering"
}
