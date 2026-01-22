variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "node_type" {
  type = string
}

variable "num_cache_nodes" {
  type    = number
  default = 1
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "altdata-${var.environment}-redis-subnet"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis" {
  name        = "altdata-${var.environment}-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "altdata-${var.environment}-redis-sg"
  }
}

resource "aws_elasticache_cluster" "main" {
  cluster_id           = "altdata-${var.environment}"
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = var.node_type
  num_cache_nodes      = var.num_cache_nodes
  parameter_group_name = "default.redis7"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  snapshot_retention_limit = var.environment == "production" ? 7 : 1
  snapshot_window         = "05:00-06:00"
  maintenance_window      = "sun:06:00-sun:07:00"

  tags = {
    Name = "altdata-${var.environment}-redis"
  }
}

output "endpoint" {
  value = aws_elasticache_cluster.main.cache_nodes[0].address
}

output "connection_string" {
  value = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379"
}
