# 🚀 Production Deployment Guide

This guide covers deploying the Healthcare Scheduling API to production with enterprise-grade infrastructure, monitoring, and security.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Infrastructure Overview](#infrastructure-overview)
- [Deployment Options](#deployment-options)
- [Configuration](#configuration)
- [Monitoring & Observability](#monitoring--observability)
- [Security](#security)
- [Backup & Recovery](#backup--recovery)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)

## 🔧 Prerequisites

### System Requirements

- **OS**: Ubuntu 20.04+ or CentOS 8+
- **CPU**: 4+ cores (8+ recommended)
- **RAM**: 8GB+ (16GB+ recommended)
- **Storage**: 100GB+ SSD
- **Network**: 1Gbps+ connection

### Software Dependencies

- Python 3.11+
- PostgreSQL 16+
- Redis 7+
- Docker & Docker Compose
- Nginx
- Certbot (for SSL)

## 🏗️ Infrastructure Overview

### Architecture Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   Nginx Proxy   │    │   FastAPI App   │
│   (Optional)    │────│   (SSL/TLS)     │────│   (Multiple)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                       ┌─────────────────┐              │
                       │   PostgreSQL    │──────────────┘
                       │   (Primary)     │
                       └─────────────────┘
                                │
                       ┌─────────────────┐
                       │   Redis Cache   │
                       │   (Sessions)    │
                       └─────────────────┘
                                │
                       ┌─────────────────┐
                       │   Celery        │
                       │   (Background)  │
                       └─────────────────┘
```

### Monitoring Stack

- **Prometheus**: Metrics collection
- **Grafana**: Dashboards and visualization
- **ELK Stack**: Log aggregation and analysis
- **Health Checks**: Application monitoring

## 🚀 Deployment Options

### Option 1: Automated Script Deployment

```bash
# Clone repository
git clone https://github.com/your-org/healthcare-scheduling-api.git
cd healthcare-scheduling-api

# Make deployment script executable
chmod +x scripts/deploy.sh

# Run deployment (requires root)
sudo ./scripts/deploy.sh
```

### Option 2: Docker Compose Deployment

```bash
# Copy environment configuration
cp env.production.example .env.production

# Edit configuration
nano .env.production

# Deploy with Docker Compose
docker-compose -f docker-compose.production.yml up -d

# Run database migrations
docker-compose -f docker-compose.production.yml exec api alembic upgrade head

# Seed initial data
docker-compose -f docker-compose.production.yml exec api python -m app.scripts.seed
```

### Option 3: Kubernetes Deployment

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/

# Check deployment status
kubectl get pods -n healthcare-api

# Access logs
kubectl logs -f deployment/healthcare-api -n healthcare-api
```

## ⚙️ Configuration

### Environment Variables

Create `.env.production` with the following variables:

```bash
# Environment
ENVIRONMENT=production
DEBUG=false

# Security
SECRET_KEY=your_very_secure_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/healthcare_scheduling
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50

# Monitoring
PROMETHEUS_ENABLED=true
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
LOG_LEVEL=INFO

# Performance
WORKER_PROCESSES=4
WORKER_CONNECTIONS=1000

# CORS
CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

### SSL/TLS Configuration

```bash
# Generate SSL certificate with Let's Encrypt
certbot --nginx -d your-domain.com

# Or use custom certificates
cp your-cert.crt /etc/ssl/certs/healthcare-api.crt
cp your-key.key /etc/ssl/private/healthcare-api.key
```

### Database Configuration

```sql
-- Create database and user
CREATE DATABASE healthcare_scheduling;
CREATE USER healthcare_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE healthcare_scheduling TO healthcare_user;

-- Configure connection limits
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;

-- Reload configuration
SELECT pg_reload_conf();
```

## 📊 Monitoring & Observability

### Health Check Endpoints

- **Basic Health**: `GET /health`
- **Detailed Health**: `GET /api/v1/health/detailed`
- **Readiness Probe**: `GET /api/v1/health/readiness`
- **Liveness Probe**: `GET /api/v1/health/liveness`
- **Metrics**: `GET /api/v1/health/metrics`

### Prometheus Metrics

Access Prometheus at `http://your-domain.com:9090` to view:

- HTTP request metrics
- Database connection pool stats
- Redis performance metrics
- System resource usage
- Custom business metrics

### Grafana Dashboards

Access Grafana at `http://monitoring.your-domain.com` to view:

- API performance dashboard
- System resource dashboard
- Database performance dashboard
- Error rate and response time trends

### Log Aggregation

Access Kibana at `http://monitoring.your-domain.com/kibana` to:

- Search and filter application logs
- Create custom log dashboards
- Set up log-based alerts
- Analyze error patterns

## 🔒 Security

### Security Headers

The application automatically sets security headers:

- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy: ...`

### HIPAA Compliance

- **Data Encryption**: AES-256 encryption at rest and in transit
- **Access Controls**: Role-based access control (RBAC)
- **Audit Logging**: Comprehensive audit trail
- **Data Retention**: Configurable retention policies
- **Secure Deletion**: Secure data disposal

### Network Security

```bash
# Configure firewall
ufw enable
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw deny 5432/tcp  # PostgreSQL
ufw deny 6379/tcp  # Redis

# Configure fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

## 💾 Backup & Recovery

### Automated Backups

```bash
# Create full backup
python scripts/backup.py --action backup --type full

# Create database backup only
python scripts/backup.py --action backup --type database

# List available backups
python scripts/backup.py --action list

# Restore from backup
python scripts/backup.py --action restore --backup-file /path/to/backup.sql
```

### Backup Schedule

Backups run automatically:
- **Database**: Daily at 2 AM
- **Files**: Daily at 3 AM
- **Configuration**: Weekly on Sunday at 1 AM
- **Retention**: 30 days (configurable)

### Disaster Recovery

1. **Stop services**:
   ```bash
   systemctl stop healthcare-api
   systemctl stop healthcare-celery
   ```

2. **Restore database**:
   ```bash
   python scripts/backup.py --action restore --backup-file latest_database_backup.sql
   ```

3. **Restore files**:
   ```bash
   python scripts/backup.py --action restore --backup-file latest_files_backup.tar.gz
   ```

4. **Start services**:
   ```bash
   systemctl start healthcare-api
   systemctl start healthcare-celery
   ```

## ⚡ Performance Optimization

### Database Optimization

```sql
-- Create indexes for common queries
CREATE INDEX idx_appointments_doctor_date ON appointments(doctor_id, start_time);
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_availability_doctor_date ON availability(doctor_id, date);

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM appointments WHERE doctor_id = 'uuid' AND start_time > NOW();
```

### Redis Optimization

```bash
# Configure Redis for production
echo "maxmemory 256mb" >> /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf
echo "save 900 1" >> /etc/redis/redis.conf
echo "save 300 10" >> /etc/redis/redis.conf
echo "save 60 10000" >> /etc/redis/redis.conf

# Restart Redis
systemctl restart redis-server
```

### Application Optimization

- **Connection Pooling**: Configured for optimal database connections
- **Caching**: Redis-based caching for frequently accessed data
- **Compression**: Gzip compression for API responses
- **Rate Limiting**: Prevents abuse and ensures fair usage

## 🔧 Troubleshooting

### Common Issues

#### 1. Service Won't Start

```bash
# Check service status
systemctl status healthcare-api

# View logs
journalctl -u healthcare-api -f

# Check configuration
python -c "from app.core.config import settings; print(settings.dict())"
```

#### 2. Database Connection Issues

```bash
# Test database connection
psql -h localhost -U healthcare_user -d healthcare_scheduling -c "SELECT 1;"

# Check connection pool
python -c "from app.db.base import get_db; db = next(get_db()); print(db.bind.pool.status())"
```

#### 3. Redis Connection Issues

```bash
# Test Redis connection
redis-cli ping

# Check Redis info
redis-cli info
```

#### 4. High Memory Usage

```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head

# Check application memory
python -c "from app.core.performance import resource_monitor; print(resource_monitor.get_system_metrics())"
```

#### 5. Slow Response Times

```bash
# Check slow queries
tail -f /var/log/postgresql/postgresql.log | grep "slow query"

# Check application metrics
curl http://localhost:8000/api/v1/health/metrics
```

### Log Locations

- **Application Logs**: `/var/log/healthcare-api/`
- **Nginx Logs**: `/var/log/nginx/`
- **PostgreSQL Logs**: `/var/log/postgresql/`
- **Redis Logs**: `/var/log/redis/`
- **System Logs**: `journalctl -u service-name`

### Performance Monitoring

```bash
# Check system resources
htop
iotop
nethogs

# Check database performance
psql -c "SELECT * FROM pg_stat_activity;"
psql -c "SELECT * FROM pg_stat_database;"

# Check Redis performance
redis-cli info stats
redis-cli slowlog get 10
```

## 📞 Support

For production support:

1. **Check logs** for error messages
2. **Review monitoring** dashboards
3. **Test health endpoints** for component status
4. **Check system resources** for bottlenecks
5. **Contact support team** with detailed error information

## 🔄 Updates & Maintenance

### Rolling Updates

```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Restart services
systemctl restart healthcare-api
systemctl restart healthcare-celery
```

### Zero-Downtime Deployment

```bash
# Use blue-green deployment
docker-compose -f docker-compose.production.yml up -d --scale api=2
docker-compose -f docker-compose.production.yml stop api_old
```

This production deployment guide ensures your Healthcare Scheduling API runs reliably, securely, and efficiently in a production environment. 🚀
