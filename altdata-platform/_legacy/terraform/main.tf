terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "altdata-terraform-state"
    key            = "altdata/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "altdata-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "altdata-platform"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# VPC
module "vpc" {
  source = "./modules/vpc"

  environment         = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
}

# RDS PostgreSQL
module "rds" {
  source = "./modules/rds"

  environment        = var.environment
  vpc_id            = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  db_instance_class  = var.db_instance_class
  db_name           = var.db_name
  db_username       = var.db_username
  db_password       = var.db_password
  multi_az          = var.environment == "production"
}

# ElastiCache Redis
module "elasticache" {
  source = "./modules/elasticache"

  environment        = var.environment
  vpc_id            = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  node_type         = var.redis_node_type
  num_cache_nodes   = var.environment == "production" ? 2 : 1
}

# S3 Bucket for raw data
module "s3" {
  source = "./modules/s3"

  environment = var.environment
  bucket_name = "altdata-${var.environment}-raw-data"
}

# Application Load Balancer
module "alb" {
  source = "./modules/alb"

  environment       = var.environment
  vpc_id           = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  certificate_arn   = var.certificate_arn
}

# ECS Cluster and Service
module "ecs" {
  source = "./modules/ecs"

  environment        = var.environment
  vpc_id            = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  alb_target_group_arn = module.alb.target_group_arn
  alb_security_group_id = module.alb.security_group_id

  container_image   = var.container_image
  container_port    = 8000
  cpu              = var.ecs_cpu
  memory           = var.ecs_memory
  desired_count    = var.ecs_desired_count

  database_url      = module.rds.connection_string
  redis_url        = module.elasticache.connection_string
  s3_bucket        = module.s3.bucket_name

  api_key_admin    = var.api_key_admin
  api_key_default  = var.api_key_default
}

# CloudWatch Dashboards and Alarms
module "cloudwatch" {
  source = "./modules/cloudwatch"

  environment     = var.environment
  ecs_cluster_name = module.ecs.cluster_name
  ecs_service_name = module.ecs.service_name
  alb_arn_suffix   = module.alb.arn_suffix
  rds_instance_id  = module.rds.instance_id
  sns_topic_arn    = var.sns_topic_arn
}
