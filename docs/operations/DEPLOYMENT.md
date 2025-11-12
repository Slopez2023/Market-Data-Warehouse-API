# Deployment Guide

Comprehensive guide for deploying the Market Data API to production environments.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Compose Deployment](#docker-compose-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Deployment](#cloud-deployment)
6. [Scaling](#scaling)
7. [Monitoring & Health](#monitoring--health)
8. [Backup & Recovery](#backup--recovery)
9. [Upgrade Procedure](#upgrade-procedure)

---

## Prerequisites

### Required
- Docker 20.10+ or Docker Desktop
- Docker Compose 1.29+ (for Docker Compose deployment)
- Python 3.11+ (for local testing)
- PostgreSQL 13+ (can be managed or external)
- 2GB RAM minimum (4GB recommended)

### Optional
- Kubernetes 1.20+ (for K8s deployment)
- Kubernetes Helm 3.0+ (for K8s with Helm)
- Cloud CLI (AWS CLI, gcloud, etc.)

---

## Environment Setup

### 1. Configuration File

Create `.env` file with production values:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Database
DB_HOST=market_data_db  # Docker Compose: service name
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=<STRONG_PASSWORD>  # Change this!
DB_NAME=market_data

# External APIs
POLYGON_API_KEY=<YOUR_POLYGON_API_KEY>

# Scheduler
BACKFILL_SCHEDULE_HOUR=0
BACKFILL_SCHEDULE_MINUTE=0

# Logging
LOG_LEVEL=INFO

# Security
API_KEY_HEADER=X-API-Key

# Alerts (Optional)
ALERT_EMAIL_ENABLED=true
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
ALERT_FROM_EMAIL=<YOUR_EMAIL>
ALERT_FROM_PASSWORD=<APP_PASSWORD>  # Use app-specific password
ALERT_TO_EMAILS=ops@company.com,dev@company.com
```

### 2. Security Checklist

- ✅ Change DB_PASSWORD to strong password (20+ chars, mixed case, numbers, symbols)
- ✅ Keep POLYGON_API_KEY private (not in version control)
- ✅ Use HTTPS in production
- ✅ Implement rate limiting
- ✅ Set up API key authentication
- ✅ Enable audit logging
- ✅ Configure email alerts

---

## Docker Compose Deployment

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/Slopez2023/Market-Data-Warehouse-API
cd MarketDataAPI

# 2. Setup environment
cp .env.example .env
# Edit .env with production values

# 3. Build images
docker-compose build

# 4. Start services
docker-compose up -d

# 5. Verify status
docker-compose ps
docker-compose logs -f market_data_api
```

### docker-compose.yml Structure

The provided `docker-compose.yml` includes:

```yaml
services:
  market_data_db:
    image: postgres:14-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    
  market_data_api:
    build: .
    depends_on:
      - market_data_db
    ports:
      - "8000:8000"
    
  market_data_dashboard:
    image: nginx:alpine
    volumes:
      - ./dashboard:/usr/share/nginx/html
    ports:
      - "3001:80"

volumes:
  postgres_data:
```

### Managing Services

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f market_data_api

# Stop services
docker-compose down

# Remove volumes (careful!)
docker-compose down -v

# Restart a service
docker-compose restart market_data_api

# Scale API workers
docker-compose up -d --scale market_data_api=3
```

### Accessing Services

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Dashboard**: http://localhost:3001
- **Database**: localhost:5432 (psql client)

---

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.20+)
- kubectl configured
- Container registry (Docker Hub, ECR, GCR)

### Building and Pushing Image

```bash
# 1. Build image
docker build -t <registry>/market-data-api:1.0.0 .

# 2. Push to registry
docker push <registry>/market-data-api:1.0.0
```

### Creating ConfigMap and Secret

```bash
# Create configmap for non-sensitive config
kubectl create configmap market-data-config \
  --from-literal=LOG_LEVEL=INFO \
  --from-literal=API_WORKERS=4 \
  -n market-data

# Create secret for sensitive data
kubectl create secret generic market-data-secrets \
  --from-literal=db_password=<PASSWORD> \
  --from-literal=polygon_api_key=<KEY> \
  -n market-data
```

### Deploying to Kubernetes

See `infrastructure/k8s/` directory for complete manifests:

```bash
# Create namespace
kubectl create namespace market-data

# Apply configuration
kubectl apply -f infrastructure/k8s/configmap.yaml
kubectl apply -f infrastructure/k8s/secret.yaml

# Deploy database
kubectl apply -f infrastructure/k8s/postgres-deployment.yaml
kubectl apply -f infrastructure/k8s/postgres-service.yaml

# Deploy API
kubectl apply -f infrastructure/k8s/api-deployment.yaml
kubectl apply -f infrastructure/k8s/api-service.yaml

# Check status
kubectl get pods -n market-data
kubectl get svc -n market-data
```

### Accessing Kubernetes Services

```bash
# Port forward to API
kubectl port-forward -n market-data svc/market-data-api 8000:8000

# View logs
kubectl logs -n market-data deployment/market-data-api -f

# Scale deployment
kubectl scale deployment market-data-api -n market-data --replicas=3
```

---

## Cloud Deployment

### AWS

#### Using Elastic Container Service (ECS)

```bash
# 1. Create ECR repository
aws ecr create-repository --repository-name market-data-api

# 2. Push image
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker tag market-data-api:latest <account>.dkr.ecr.<region>.amazonaws.com/market-data-api:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/market-data-api:latest

# 3. Create ECS task definition (see infrastructure/aws/ecs-task-definition.json)
aws ecs register-task-definition --cli-input-json file://infrastructure/aws/ecs-task-definition.json

# 4. Create ECS service
aws ecs create-service --cluster market-data --service-name api --task-definition market-data-api --desired-count 2
```

#### Using RDS for Database

```bash
# Create RDS PostgreSQL instance
aws rds create-db-instance \
  --db-instance-identifier market-data-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 14.7 \
  --master-username postgres \
  --master-user-password <PASSWORD> \
  --allocated-storage 100
```

### Google Cloud Platform (GCP)

#### Using Cloud Run

```bash
# 1. Push to Google Container Registry
docker tag market-data-api gcr.io/<project>/market-data-api
docker push gcr.io/<project>/market-data-api

# 2. Deploy to Cloud Run
gcloud run deploy market-data-api \
  --image gcr.io/<project>/market-data-api \
  --platform managed \
  --region us-central1 \
  --set-env-vars DB_HOST=<cloudsql-proxy> \
  --allow-unauthenticated
```

#### Using Cloud SQL for Database

```bash
# Create Cloud SQL instance
gcloud sql instances create market-data-db \
  --database-version=POSTGRES_14 \
  --tier=db-n1-standard-2 \
  --region=us-central1
```

### Azure

#### Using Container Instances

```bash
# Push to Azure Container Registry
az acr build --registry <registry-name> --image market-data-api:1.0.0 .

# Deploy container instance
az container create \
  --resource-group <group> \
  --name market-data-api \
  --image <registry>.azurecr.io/market-data-api:1.0.0 \
  --environment-variables DB_HOST=<host> \
  --ports 8000
```

---

## Scaling

### Horizontal Scaling (Multiple API Instances)

#### Docker Compose

```bash
# Scale to 3 instances
docker-compose up -d --scale market_data_api=3

# With load balancer (nginx)
# Add to docker-compose.yml:
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
  depends_on:
    - market_data_api
```

#### Kubernetes

```bash
# Scale deployment
kubectl scale deployment market-data-api --replicas=5

# Use Horizontal Pod Autoscaler
kubectl autoscale deployment market-data-api --min=2 --max=10 --cpu-percent=70
```

### Vertical Scaling (Increase Resources)

#### Docker
```bash
# Edit docker-compose.yml
services:
  market_data_api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

#### Configuration Optimization
```bash
# Increase workers
API_WORKERS=8

# Increase database connections
DB_POOL_SIZE=20

# Increase cache size
QUERY_CACHE_MAX_SIZE=5000
```

### Database Scaling

#### Read Replicas

```sql
-- PostgreSQL streaming replication
-- Primary server: postgresql.conf
max_wal_senders = 10
wal_level = replica

-- Replica server
SELECT * FROM pg_basebackup(
  format => 'tar', 
  label => 'base backup'
)
```

#### Optimization

```sql
-- Create indexes
CREATE INDEX idx_ohlcv_symbol_timeframe ON ohlcv (symbol, timeframe, timestamp);
CREATE INDEX idx_ohlcv_quality ON ohlcv (quality_score) WHERE quality_score > 0.85;

-- Analyze table
ANALYZE ohlcv;

-- Check slow queries
SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;
```

---

## Monitoring & Health

### Health Check Endpoints

```bash
# Basic health
curl http://localhost:8000/health

# Full system status
curl http://localhost:8000/api/v1/status

# Metrics
curl http://localhost:8000/api/v1/metrics

# Performance
curl http://localhost:8000/api/v1/performance/summary
```

### Container Monitoring

```bash
# Docker logs
docker logs -f market_data_api

# Docker stats
docker stats market_data_api

# System metrics
docker inspect market_data_api
```

### Database Monitoring

```bash
# Connect to database
docker exec -it market_data_db psql -U postgres -d market_data

# Check connections
SELECT count(*) FROM pg_stat_activity;

# Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables ORDER BY pg_total_relation_size DESC;

# Backups
SELECT * FROM backfill_history ORDER BY start_time DESC LIMIT 10;
```

### Alerts

#### Email Alerts

```bash
# Configure in .env
ALERT_EMAIL_ENABLED=true
ALERT_TO_EMAILS=ops@company.com
```

#### Prometheus Integration (Optional)

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'market_data_api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/observability/metrics'
```

---

## Backup & Recovery

### Database Backups

#### Using pg_dump

```bash
# Full backup
docker exec market_data_db pg_dump -U postgres market_data > backup.sql

# Compressed backup
docker exec market_data_db pg_dump -U postgres market_data | gzip > backup.sql.gz

# Restore
docker exec -i market_data_db psql -U postgres market_data < backup.sql
```

#### Scheduled Backups

```bash
# Cron job for daily backups
0 2 * * * docker exec market_data_db pg_dump -U postgres market_data | gzip > /backups/market_data_$(date +\%Y\%m\%d).sql.gz

# Cleanup old backups (keep 7 days)
find /backups -name "market_data_*.sql.gz" -mtime +7 -delete
```

### Volume Backups

```bash
# Backup Docker volume
docker run --rm -v market_data_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data

# Restore volume backup
docker run --rm -v market_data_postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /
```

---

## Upgrade Procedure

### Pre-Upgrade Checklist

- ✅ Create database backup
- ✅ Test upgrade in staging environment
- ✅ Review release notes
- ✅ Plan maintenance window
- ✅ Notify stakeholders

### Upgrade Steps

#### Docker Compose

```bash
# 1. Stop services
docker-compose down

# 2. Backup database
docker run --rm -v market_data_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/pre-upgrade-backup.tar.gz /data

# 3. Pull latest code
git pull origin main

# 4. Build new image
docker-compose build

# 5. Apply migrations (if needed)
docker-compose run --rm market_data_api python -m alembic upgrade head

# 6. Start services
docker-compose up -d

# 7. Verify
curl http://localhost:8000/health
```

#### Kubernetes

```bash
# 1. Create backup
kubectl exec -n market-data <pod> -- pg_dump -U postgres market_data > pre-upgrade.sql

# 2. Update image in deployment
kubectl set image deployment/market-data-api \
  -n market-data \
  market_data_api=<registry>/market-data-api:new-version

# 3. Monitor rollout
kubectl rollout status deployment/market-data-api -n market-data

# 4. Rollback if needed
kubectl rollout undo deployment/market-data-api -n market-data
```

### Post-Upgrade Validation

```bash
# Health check
curl http://localhost:8000/health

# Database integrity
curl http://localhost:8000/api/v1/status

# Run tests
docker-compose exec market_data_api pytest tests/ -v

# Check logs
docker-compose logs market_data_api
```

---

## Production Checklist

- ✅ Use strong passwords (DB_PASSWORD, ALERT email password)
- ✅ Enable HTTPS/TLS
- ✅ Configure API key authentication
- ✅ Set up monitoring and alerts
- ✅ Implement backup strategy
- ✅ Use managed databases when possible
- ✅ Set resource limits
- ✅ Configure health checks
- ✅ Use persistent volumes
- ✅ Plan for scaling
- ✅ Document runbooks
- ✅ Test disaster recovery

---

## Troubleshooting

See [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md) for common deployment issues.

---

## Support

- [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md)
- [Monitoring Guide](/docs/operations/MONITORING.md)
- [Operations Overview](/docs/operations/README.md)
- [FAQ](/docs/reference/FAQ.md)
