# 🏗️ Healthcare Scheduling API - Architecture Documentation

## Overview

This directory contains comprehensive architecture documentation for the Healthcare Scheduling API, including system design, database schema, API structure, and deployment strategies.

## 📁 Architecture Documents

### **System Architecture**
- **[System Architecture](./system-architecture.md)** - High-level system design, component relationships, and technology stack
- **[Database Schema](./database-schema.md)** - Complete database design, relationships, and optimization strategies
- **[API Architecture](./api-architecture.md)** - REST API design, endpoints, security, and documentation
- **[Deployment Architecture](./deployment-architecture.md)** - Infrastructure, deployment strategies, and scaling

## 🎯 Quick Reference

### **Architecture Principles**
- **Microservices**: Modular, scalable service architecture
- **Security-First**: HIPAA compliance and data protection
- **High Availability**: Multi-instance deployment with failover
- **Observability**: Comprehensive monitoring and logging
- **Scalability**: Horizontal and vertical scaling capabilities

### **Technology Stack**
| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | React/Vue.js | User interface |
| **API Gateway** | Nginx | Load balancing, SSL termination |
| **Backend** | FastAPI (Python 3.11) | REST API server |
| **Database** | PostgreSQL 16 | Primary data storage |
| **Cache** | Redis 7 | Caching and sessions |
| **Background** | Celery | Asynchronous task processing |
| **Monitoring** | Prometheus + Grafana | Metrics and dashboards |
| **Logging** | ELK Stack | Log aggregation |
| **Container** | Docker | Application containerization |
| **Orchestration** | Docker Compose/K8s | Container orchestration |

### **Key Features**
- ✅ **HIPAA Compliant**: Healthcare data protection
- ✅ **High Performance**: Optimized for speed and scalability
- ✅ **Secure**: Multi-layer security architecture
- ✅ **Monitored**: Comprehensive observability
- ✅ **Scalable**: Auto-scaling and load balancing
- ✅ **Resilient**: Fault tolerance and disaster recovery

## 🚀 Quick Start

### **Development Environment**
```bash
# Clone repository
git clone https://github.com/your-org/healthcare-scheduling-api.git
cd healthcare-scheduling-api

# Start development environment
make run
```

### **Production Deployment**
```bash
# Automated deployment
sudo ./scripts/deploy.sh

# Docker Compose deployment
make prod-up

# Kubernetes deployment
kubectl apply -f k8s/
```

## 📊 Architecture Diagrams

### **System Overview**
```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Application]
        MOBILE[Mobile App]
        API_CLIENT[API Client]
    end
    
    subgraph "API Gateway"
        NGINX[Nginx + SSL]
    end
    
    subgraph "Application Layer"
        API[FastAPI Instances]
        WORKER[Celery Workers]
    end
    
    subgraph "Data Layer"
        POSTGRES[(PostgreSQL)]
        REDIS[(Redis)]
    end
    
    subgraph "Monitoring"
        PROMETHEUS[Prometheus]
        GRAFANA[Grafana]
    end
    
    WEB --> NGINX
    MOBILE --> NGINX
    API_CLIENT --> NGINX
    NGINX --> API
    API --> POSTGRES
    API --> REDIS
    WORKER --> POSTGRES
    WORKER --> REDIS
    API --> PROMETHEUS
    PROMETHEUS --> GRAFANA
```

### **Security Architecture**
```mermaid
graph TB
    subgraph "External Security"
        WAF[Web Application Firewall]
        DDoS[DDoS Protection]
    end
    
    subgraph "Application Security"
        SSL[SSL/TLS]
        AUTH[Authentication]
        RBAC[Authorization]
    end
    
    subgraph "Data Security"
        ENCRYPT[Encryption at Rest]
        AUDIT[Audit Logging]
    end
    
    WAF --> SSL
    DDoS --> SSL
    SSL --> AUTH
    AUTH --> RBAC
    RBAC --> ENCRYPT
    ENCRYPT --> AUDIT
```

## 🔧 Configuration

### **Environment Variables**
```bash
# Core Configuration
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/db
REDIS_URL=redis://localhost:6379/0

# Monitoring
PROMETHEUS_ENABLED=true
LOG_LEVEL=INFO
```

### **Docker Compose**
```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/db
      - REDIS_URL=redis://redis:6379/0
  
  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=healthcare_scheduling
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
  
  redis:
    image: redis:7-alpine
```

## 📈 Monitoring

### **Health Checks**
- **Basic**: `GET /health`
- **Detailed**: `GET /api/v1/health/detailed`
- **Readiness**: `GET /api/v1/health/readiness`
- **Liveness**: `GET /api/v1/health/liveness`

### **Metrics**
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000`
- **API Metrics**: `GET /metrics`

### **Logging**
- **Application Logs**: Structured JSON logging
- **Access Logs**: Nginx access logs
- **Error Logs**: Application error logs
- **Audit Logs**: Security and compliance logs

## 🔒 Security

### **Authentication**
- JWT tokens with refresh mechanism
- OAuth2 password flow
- Role-based access control (RBAC)

### **Data Protection**
- AES-256 encryption at rest
- TLS 1.3 for data in transit
- HIPAA compliance features
- Comprehensive audit logging

### **Network Security**
- WAF protection
- Rate limiting
- CORS configuration
- Security headers

## 📚 Additional Resources

- **[API Documentation](../README.md#api-documentation)** - Complete API reference
- **[Production Deployment](../PRODUCTION_DEPLOYMENT.md)** - Production setup guide
- **[HIPAA Compliance](../HIPAA_COMPLIANCE.md)** - Security and compliance
- **[Development Guide](../README.md#development)** - Development setup

## 🤝 Contributing

When contributing to the architecture:

1. **Update diagrams** when changing system design
2. **Document changes** in relevant architecture files
3. **Test deployments** in staging environment
4. **Review security** implications of changes
5. **Update documentation** for new features

## 📞 Support

For architecture questions:

- **Documentation**: Check relevant architecture files
- **Issues**: Create GitHub issue with architecture label
- **Discussions**: Use GitHub discussions for questions
- **Security**: Report security issues privately

---

**Status**: Production Ready ✅
