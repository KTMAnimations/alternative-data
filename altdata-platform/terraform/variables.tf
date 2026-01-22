variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (staging/production)"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# Database
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "altdata"
}

variable "db_username" {
  description = "Database username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

# Redis
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

# ECS
variable "container_image" {
  description = "Container image URI"
  type        = string
}

variable "ecs_cpu" {
  description = "ECS task CPU"
  type        = number
  default     = 512
}

variable "ecs_memory" {
  description = "ECS task memory"
  type        = number
  default     = 1024
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

# SSL
variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS"
  type        = string
}

# API Keys
variable "api_key_admin" {
  description = "Admin API key"
  type        = string
  sensitive   = true
}

variable "api_key_default" {
  description = "Default API key"
  type        = string
  sensitive   = true
}

# Alerts
variable "sns_topic_arn" {
  description = "SNS topic ARN for alerts"
  type        = string
  default     = ""
}
