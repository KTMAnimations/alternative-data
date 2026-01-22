# Deployment Guide

Quick reference for deploying the Alternative Data Platform to staging and production.

## Local Development

```bash
# Start services
docker-compose up -d

# Run API
uvicorn src.api.main:app --reload

# Access
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
# PostgreSQL: localhost:5432
# Redis: localhost:6379
```

## Staging Deployment (AWS)

### 1. Infrastructure Setup (Terraform or Console)

```hcl
# Required resources:
# - RDS PostgreSQL 15 with TimescaleDB (db.t3.medium)
# - ElastiCache Redis (cache.t3.micro)
# - ECS Fargate cluster
# - Application Load Balancer
# - S3 bucket for raw data
# - ECR for container images
```

### 2. Build and Push Docker Image

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin \
    123456789.dkr.ecr.us-east-1.amazonaws.com

# Build
docker build -t altdata-platform:latest .

# Tag
docker tag altdata-platform:latest \
    123456789.dkr.ecr.us-east-1.amazonaws.com/altdata-platform:latest

# Push
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/altdata-platform:latest
```

### 3. ECS Task Definition

```json
{
  "family": "altdata-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::123456789:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/altdata-platform:latest",
      "portMappings": [
        {"containerPort": 8000, "protocol": "tcp"}
      ],
      "environment": [
        {"name": "ENVIRONMENT", "value": "staging"},
        {"name": "DATABASE_URL", "value": "postgresql://..."},
        {"name": "REDIS_URL", "value": "redis://..."}
      ],
      "secrets": [
        {"name": "FRED_API_KEY", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "ADSB_API_KEY", "valueFrom": "arn:aws:secretsmanager:..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/altdata",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "api"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

### 4. Create ECS Service

```bash
aws ecs create-service \
    --cluster altdata-cluster \
    --service-name altdata-api \
    --task-definition altdata-api:1 \
    --desired-count 2 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=api,containerPort=8000"
```

### 5. Configure ALB Health Check

- Path: `/health`
- Healthy threshold: 2
- Unhealthy threshold: 3
- Timeout: 5s
- Interval: 30s

## Production Deployment

### Additional Steps for Production

1. **Enable Auto-Scaling**
```bash
aws application-autoscaling register-scalable-target \
    --service-namespace ecs \
    --scalable-dimension ecs:service:DesiredCount \
    --resource-id service/altdata-cluster/altdata-api \
    --min-capacity 2 \
    --max-capacity 10
```

2. **Set Up CloudWatch Alarms**
- CPU > 70% → Scale up
- Request latency > 500ms → Alert
- Error rate > 1% → Alert
- Database connections > 80% → Alert

3. **Enable WAF**
- Rate limiting: 1000 requests/IP/5min
- SQL injection protection
- Geo-blocking if needed

4. **Set Up Backups**
- RDS: Automated daily backups (7-day retention)
- S3: Cross-region replication
- ElastiCache: Daily snapshots

## Environment Variables

### Required
```bash
DATABASE_URL=postgresql://user:pass@host:5432/altdata
REDIS_URL=redis://host:6379/0
SEC_EDGAR_USER_AGENT=YourCompany contact@company.com
```

### API Keys
```bash
FRED_API_KEY=xxx
ADSB_EXCHANGE_API_KEY=xxx
ADSB_EXCHANGE_RAPIDAPI_KEY=xxx
OPENAQ_API_KEY=xxx
USPTO_API_KEY=xxx
```

### Optional
```bash
SENTRY_DSN=https://xxx@sentry.io/xxx
LOG_LEVEL=INFO
API_KEY_ADMIN=xxx
```

## Database Migrations

```bash
# On deployment, run migrations
alembic upgrade head

# If rollback needed
alembic downgrade -1
```

## Monitoring Checklist

- [ ] CloudWatch dashboards configured
- [ ] Alerts set up (Slack/PagerDuty)
- [ ] Log aggregation working
- [ ] APM tracing enabled (X-Ray/Datadog)
- [ ] Uptime monitoring (StatusPage/Pingdom)

## Rollback Procedure

1. **Identify the issue**
   - Check CloudWatch logs
   - Check error rates
   - Check latency

2. **Quick rollback**
```bash
# Revert to previous task definition
aws ecs update-service \
    --cluster altdata-cluster \
    --service altdata-api \
    --task-definition altdata-api:PREVIOUS_VERSION
```

3. **Database rollback if needed**
```bash
alembic downgrade -1
```

## Cost Estimates (AWS)

| Resource | Staging | Production |
|----------|---------|------------|
| RDS (db.t3.medium) | $50/mo | $200/mo (multi-AZ) |
| ElastiCache | $15/mo | $60/mo (multi-AZ) |
| ECS Fargate (2 tasks) | $30/mo | $120/mo (4 tasks) |
| ALB | $20/mo | $20/mo |
| S3 (100GB) | $3/mo | $3/mo |
| CloudWatch | $10/mo | $30/mo |
| **Total** | **~$130/mo** | **~$430/mo** |

## Security Checklist

- [ ] All secrets in Secrets Manager
- [ ] Database not publicly accessible
- [ ] API keys rotated quarterly
- [ ] TLS 1.2+ enforced
- [ ] VPC properly configured
- [ ] Security groups minimal
- [ ] IAM roles least-privilege
