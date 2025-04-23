# 🏗️ Healthcare Scheduling API - System Architecture

## Overview

The Healthcare Scheduling API is built with a microservices architecture designed for high availability, scalability, and HIPAA compliance.

## High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Application]
        MOBILE[Mobile App]
        API_CLIENT[API Client]
    end
    
    subgraph "Load Balancer Layer"
        LB[Load Balancer<br/>Nginx/HAProxy]
    end
    
    subgraph "API Gateway Layer"
        NGINX[Nginx Reverse Proxy<br/>SSL Termination<br/>Rate Limiting]
    end
    
    subgraph "Application Layer"
        API1[FastAPI Instance 1]
        API2[FastAPI Instance 2]
        API3[FastAPI Instance N]
    end
    
    subgraph "Background Processing"
        CELERY1[Celery Worker 1]
        CELERY2[Celery Worker 2]
        CELERY_BEAT[Celery Beat Scheduler]
    end
    
    subgraph "Data Layer"
        POSTGRES[(PostgreSQL<br/>Primary Database)]
        REDIS[(Redis<br/>Cache & Sessions)]
    end
    
    subgraph "Monitoring & Observability"
        PROMETHEUS[Prometheus<br/>Metrics Collection]
        GRAFANA[Grafana<br/>Dashboards]
        ELK[ELK Stack<br/>Log Aggregation]
    end
    
    subgraph "External Services"
        EMAIL[Email Service<br/>SMTP/SendGrid]
        SMS[SMS Service<br/>Twilio]
        STORAGE[File Storage<br/>S3/MinIO]
    end
    
    %% Client connections
    WEB --> LB
    MOBILE --> LB
    API_CLIENT --> LB
    
    %% Load balancer to API gateway
    LB --> NGINX
    
    %% API gateway to application instances
    NGINX --> API1
    NGINX --> API2
    NGINX --> API3
    
    %% Application to data layer
    API1 --> POSTGRES
    API2 --> POSTGRES
    API3 --> POSTGRES
    
    API1 --> REDIS
    API2 --> REDIS
    API3 --> REDIS
    
    %% Background processing
    CELERY1 --> POSTGRES
    CELERY1 --> REDIS
    CELERY2 --> POSTGRES
    CELERY2 --> REDIS
    CELERY_BEAT --> REDIS
    
    %% Monitoring connections
    API1 --> PROMETHEUS
    API2 --> PROMETHEUS
    API3 --> PROMETHEUS
    PROMETHEUS --> GRAFANA
    
    %% Logging
    API1 --> ELK
    API2 --> ELK
    API3 --> ELK
    CELERY1 --> ELK
    CELERY2 --> ELK
    
    %% External services
    API1 --> EMAIL
    API1 --> SMS
    API1 --> STORAGE
    CELERY1 --> EMAIL
    CELERY1 --> SMS
    
    %% Styling
    classDef clientLayer fill:#e1f5fe
    classDef loadBalancer fill:#f3e5f5
    classDef apiLayer fill:#e8f5e8
    classDef dataLayer fill:#fff3e0
    classDef monitoring fill:#fce4ec
    classDef external fill:#f1f8e9
    
    class WEB,MOBILE,API_CLIENT clientLayer
    class LB,NGINX loadBalancer
    class API1,API2,API3,CELERY1,CELERY2,CELERY_BEAT apiLayer
    class POSTGRES,REDIS dataLayer
    class PROMETHEUS,GRAFANA,ELK monitoring
    class EMAIL,SMS,STORAGE external
```

## Component Details

### **Client Layer**
- **Web Application**: React/Vue.js frontend
- **Mobile App**: iOS/Android applications
- **API Client**: Third-party integrations

### **Load Balancer Layer**
- **Load Balancer**: Distributes traffic across API instances
- **Health Checks**: Monitors backend service health
- **SSL Termination**: Handles HTTPS encryption

### **API Gateway Layer**
- **Nginx Reverse Proxy**: Request routing and load balancing
- **Rate Limiting**: Prevents API abuse
- **Security Headers**: HIPAA compliance headers
- **CORS Management**: Cross-origin request handling

### **Application Layer**
- **FastAPI Instances**: Multiple API server instances
- **Celery Workers**: Background task processing
- **Celery Beat**: Scheduled task management
- **Auto-scaling**: Dynamic instance scaling based on load

### **Data Layer**
- **PostgreSQL**: Primary relational database
- **Redis**: Caching and session storage
- **Connection Pooling**: Optimized database connections
- **Backup Strategy**: Automated backups with point-in-time recovery

### **Monitoring & Observability**
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization and dashboards
- **ELK Stack**: Log aggregation and analysis
- **Health Checks**: Comprehensive system monitoring

### **External Services**
- **Email Service**: Appointment reminders and notifications
- **SMS Service**: Text message notifications
- **File Storage**: Document and image storage

## Security Architecture

```mermaid
graph TB
    subgraph "External Security"
        WAF[Web Application Firewall]
        DDoS[DDoS Protection]
    end
    
    subgraph "Network Security"
        VPN[VPN Gateway]
        FIREWALL[Network Firewall]
    end
    
    subgraph "Application Security"
        AUTH[Authentication<br/>JWT Tokens]
        RBAC[Role-Based Access Control]
        ENCRYPT[Data Encryption<br/>AES-256]
    end
    
    subgraph "Data Security"
        DB_ENCRYPT[Database Encryption<br/>at Rest]
        BACKUP_ENCRYPT[Encrypted Backups]
        AUDIT[Audit Logging]
    end
    
    subgraph "Compliance"
        HIPAA[HIPAA Compliance]
        SOC2[SOC 2 Type II]
        GDPR[GDPR Compliance]
    end
    
    WAF --> VPN
    DDoS --> VPN
    VPN --> FIREWALL
    FIREWALL --> AUTH
    AUTH --> RBAC
    RBAC --> ENCRYPT
    ENCRYPT --> DB_ENCRYPT
    DB_ENCRYPT --> BACKUP_ENCRYPT
    BACKUP_ENCRYPT --> AUDIT
    AUDIT --> HIPAA
    HIPAA --> SOC2
    SOC2 --> GDPR
```

## Deployment Architecture

### **Development Environment**
```mermaid
graph LR
    DEV[Developer Machine] --> DOCKER[Docker Compose]
    DOCKER --> API[FastAPI Dev]
    DOCKER --> DB[PostgreSQL]
    DOCKER --> REDIS[Redis]
    DOCKER --> WORKER[Celery Worker]
```

### **Staging Environment**
```mermaid
graph TB
    subgraph "Staging Infrastructure"
        STAGING_LB[Load Balancer]
        STAGING_API[API Instances]
        STAGING_DB[PostgreSQL]
        STAGING_REDIS[Redis]
        STAGING_MONITOR[Monitoring]
    end
    
    CI[CI/CD Pipeline] --> STAGING_LB
    STAGING_LB --> STAGING_API
    STAGING_API --> STAGING_DB
    STAGING_API --> STAGING_REDIS
    STAGING_API --> STAGING_MONITOR
```

### **Production Environment**
```mermaid
graph TB
    subgraph "Production Infrastructure"
        PROD_LB[Load Balancer<br/>High Availability]
        PROD_API[API Instances<br/>Auto-scaling]
        PROD_DB[PostgreSQL<br/>Primary + Replica]
        PROD_REDIS[Redis<br/>Cluster Mode]
        PROD_MONITOR[Full Monitoring Stack]
        PROD_BACKUP[Automated Backups]
    end
    
    CD[Continuous Deployment] --> PROD_LB
    PROD_LB --> PROD_API
    PROD_API --> PROD_DB
    PROD_API --> PROD_REDIS
    PROD_API --> PROD_MONITOR
    PROD_DB --> PROD_BACKUP
```

## Data Flow Architecture

```mermaid
sequenceDiagram
    participant Client
    participant LB as Load Balancer
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Redis
    participant Celery
    participant External as External Services
    
    Client->>LB: HTTPS Request
    LB->>API: HTTP Request
    API->>Redis: Check Cache
    alt Cache Hit
        Redis-->>API: Cached Data
    else Cache Miss
        API->>DB: Database Query
        DB-->>API: Query Result
        API->>Redis: Store in Cache
    end
    API-->>LB: JSON Response
    LB-->>Client: HTTPS Response
    
    Note over API,Celery: Background Processing
    API->>Celery: Queue Task
    Celery->>DB: Process Task
    Celery->>External: Send Notification
    Celery->>Redis: Update Status
```

## Scalability Architecture

```mermaid
graph TB
    subgraph "Horizontal Scaling"
        HORIZONTAL[Auto-scaling Groups]
        HORIZONTAL --> API_SCALE[API Instances<br/>1-N instances]
        HORIZONTAL --> WORKER_SCALE[Celery Workers<br/>1-N workers]
    end
    
    subgraph "Vertical Scaling"
        VERTICAL[Resource Optimization]
        VERTICAL --> CPU[CPU Scaling]
        VERTICAL --> MEMORY[Memory Scaling]
        VERTICAL --> STORAGE[Storage Scaling]
    end
    
    subgraph "Database Scaling"
        DB_SCALE[Database Optimization]
        DB_SCALE --> READ_REPLICA[Read Replicas]
        DB_SCALE --> CONNECTION_POOL[Connection Pooling]
        DB_SCALE --> QUERY_OPT[Query Optimization]
    end
    
    subgraph "Cache Scaling"
        CACHE_SCALE[Redis Scaling]
        CACHE_SCALE --> REDIS_CLUSTER[Redis Cluster]
        CACHE_SCALE --> CACHE_STRATEGY[Cache Strategy]
    end
```

## Technology Stack

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
| **CI/CD** | GitHub Actions | Continuous integration/deployment |
