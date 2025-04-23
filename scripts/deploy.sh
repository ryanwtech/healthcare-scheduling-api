#!/bin/bash
# Production deployment script for Healthcare Scheduling API

set -e  # Exit on any error

# Configuration
APP_NAME="healthcare-scheduling-api"
APP_DIR="/opt/healthcare-api"
SERVICE_USER="healthcare"
SERVICE_GROUP="healthcare"
PYTHON_VERSION="3.11"
VENV_DIR="/opt/healthcare-api/venv"
LOG_DIR="/var/log/healthcare-api"
BACKUP_DIR="/opt/backups/healthcare-api"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Create system user and group
create_user() {
    log_info "Creating system user and group..."
    
    if ! getent group $SERVICE_GROUP > /dev/null 2>&1; then
        groupadd $SERVICE_GROUP
        log_success "Created group: $SERVICE_GROUP"
    fi
    
    if ! getent passwd $SERVICE_USER > /dev/null 2>&1; then
        useradd -r -g $SERVICE_GROUP -d $APP_DIR -s /bin/false $SERVICE_USER
        log_success "Created user: $SERVICE_USER"
    fi
}

# Install system dependencies
install_dependencies() {
    log_info "Installing system dependencies..."
    
    # Update package list
    apt-get update
    
    # Install required packages
    apt-get install -y \
        python$PYTHON_VERSION \
        python$PYTHON_VERSION-venv \
        python$PYTHON_VERSION-dev \
        build-essential \
        libpq-dev \
        redis-server \
        postgresql-client \
        nginx \
        supervisor \
        certbot \
        python3-certbot-nginx \
        curl \
        wget \
        git \
        htop \
        vim \
        ufw \
        fail2ban
    
    log_success "System dependencies installed"
}

# Setup application directory
setup_app_directory() {
    log_info "Setting up application directory..."
    
    # Create directories
    mkdir -p $APP_DIR
    mkdir -p $LOG_DIR
    mkdir -p $BACKUP_DIR
    mkdir -p /etc/healthcare-api
    
    # Set ownership
    chown -R $SERVICE_USER:$SERVICE_GROUP $APP_DIR
    chown -R $SERVICE_USER:$SERVICE_GROUP $LOG_DIR
    chown -R $SERVICE_USER:$SERVICE_GROUP $BACKUP_DIR
    
    log_success "Application directory setup complete"
}

# Deploy application code
deploy_application() {
    log_info "Deploying application code..."
    
    # Clone or update repository
    if [ -d "$APP_DIR/.git" ]; then
        cd $APP_DIR
        git pull origin main
    else
        git clone https://github.com/your-org/healthcare-scheduling-api.git $APP_DIR
        cd $APP_DIR
    fi
    
    # Create virtual environment
    if [ ! -d "$VENV_DIR" ]; then
        python$PYTHON_VERSION -m venv $VENV_DIR
    fi
    
    # Activate virtual environment and install dependencies
    source $VENV_DIR/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Set ownership
    chown -R $SERVICE_USER:$SERVICE_GROUP $APP_DIR
    
    log_success "Application deployed"
}

# Setup database
setup_database() {
    log_info "Setting up database..."
    
    # Create database and user
    sudo -u postgres psql << EOF
CREATE DATABASE healthcare_scheduling;
CREATE USER healthcare_user WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE healthcare_scheduling TO healthcare_user;
\q
EOF
    
    # Run migrations
    cd $APP_DIR
    source $VENV_DIR/bin/activate
    export DATABASE_URL="postgresql://healthcare_user:secure_password_here@localhost/healthcare_scheduling"
    alembic upgrade head
    
    log_success "Database setup complete"
}

# Configure Redis
configure_redis() {
    log_info "Configuring Redis..."
    
    # Update Redis configuration
    cat > /etc/redis/redis.conf << EOF
# Healthcare API Redis Configuration
bind 127.0.0.1
port 6379
timeout 300
tcp-keepalive 60
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
EOF
    
    # Restart Redis
    systemctl restart redis-server
    systemctl enable redis-server
    
    log_success "Redis configured"
}

# Setup systemd services
setup_services() {
    log_info "Setting up systemd services..."
    
    # API service
    cat > /etc/systemd/system/healthcare-api.service << EOF
[Unit]
Description=Healthcare Scheduling API
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=exec
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin
Environment=ENVIRONMENT=production
Environment=DATABASE_URL=postgresql://healthcare_user:secure_password_here@localhost/healthcare_scheduling
Environment=REDIS_URL=redis://localhost:6379/0
Environment=SECRET_KEY=your_secret_key_here
ExecStart=$VENV_DIR/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=healthcare-api

[Install]
WantedBy=multi-user.target
EOF
    
    # Celery worker service
    cat > /etc/systemd/system/healthcare-celery.service << EOF
[Unit]
Description=Healthcare API Celery Worker
After=network.target redis.service
Requires=redis.service

[Service]
Type=exec
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin
Environment=ENVIRONMENT=production
Environment=DATABASE_URL=postgresql://healthcare_user:secure_password_here@localhost/healthcare_scheduling
Environment=REDIS_URL=redis://localhost:6379/0
Environment=CELERY_BROKER_URL=redis://localhost:6379/0
Environment=CELERY_RESULT_BACKEND=redis://localhost:6379/0
ExecStart=$VENV_DIR/bin/celery -A app.workers.celery_app worker --loglevel=info --concurrency=4
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=healthcare-celery

[Install]
WantedBy=multi-user.target
EOF
    
    # Celery beat service (for scheduled tasks)
    cat > /etc/systemd/system/healthcare-celery-beat.service << EOF
[Unit]
Description=Healthcare API Celery Beat
After=network.target redis.service
Requires=redis.service

[Service]
Type=exec
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin
Environment=ENVIRONMENT=production
Environment=DATABASE_URL=postgresql://healthcare_user:secure_password_here@localhost/healthcare_scheduling
Environment=REDIS_URL=redis://localhost:6379/0
Environment=CELERY_BROKER_URL=redis://localhost:6379/0
Environment=CELERY_RESULT_BACKEND=redis://localhost:6379/0
ExecStart=$VENV_DIR/bin/celery -A app.workers.celery_app beat --loglevel=info
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=healthcare-celery-beat

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and enable services
    systemctl daemon-reload
    systemctl enable healthcare-api
    systemctl enable healthcare-celery
    systemctl enable healthcare-celery-beat
    
    log_success "Systemd services configured"
}

# Configure Nginx
configure_nginx() {
    log_info "Configuring Nginx..."
    
    # Remove default site
    rm -f /etc/nginx/sites-enabled/default
    
    # Create Nginx configuration
    cat > /etc/nginx/sites-available/healthcare-api << EOF
upstream healthcare_api {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Rate limiting
    limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
    
    # Client settings
    client_max_body_size 10M;
    client_body_timeout 60s;
    client_header_timeout 60s;
    
    # Proxy settings
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    proxy_buffering on;
    proxy_buffer_size 4k;
    proxy_buffers 8 4k;
    
    # API routes
    location / {
        proxy_pass http://healthcare_api;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # Static files (if any)
    location /static/ {
        alias $APP_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://healthcare_api;
        access_log off;
    }
    
    # Metrics endpoint (restricted)
    location /metrics {
        proxy_pass http://healthcare_api;
        allow 127.0.0.1;
        deny all;
    }
}
EOF
    
    # Enable site
    ln -sf /etc/nginx/sites-available/healthcare-api /etc/nginx/sites-enabled/
    
    # Test configuration
    nginx -t
    
    # Restart Nginx
    systemctl restart nginx
    systemctl enable nginx
    
    log_success "Nginx configured"
}

# Setup SSL with Let's Encrypt
setup_ssl() {
    log_info "Setting up SSL with Let's Encrypt..."
    
    # Install certbot
    apt-get install -y certbot python3-certbot-nginx
    
    # Get SSL certificate
    certbot --nginx -d your-domain.com --non-interactive --agree-tos --email admin@your-domain.com
    
    # Setup auto-renewal
    echo "0 12 * * * /usr/bin/certbot renew --quiet" | crontab -
    
    log_success "SSL configured"
}

# Configure firewall
configure_firewall() {
    log_info "Configuring firewall..."
    
    # Reset UFW
    ufw --force reset
    
    # Default policies
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow SSH
    ufw allow ssh
    
    # Allow HTTP and HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    # Allow PostgreSQL (only from localhost)
    ufw allow from 127.0.0.1 to any port 5432
    
    # Allow Redis (only from localhost)
    ufw allow from 127.0.0.1 to any port 6379
    
    # Enable firewall
    ufw --force enable
    
    log_success "Firewall configured"
}

# Setup monitoring
setup_monitoring() {
    log_info "Setting up monitoring..."
    
    # Install monitoring tools
    apt-get install -y htop iotop nethogs
    
    # Create monitoring script
    cat > /usr/local/bin/healthcare-monitor.sh << 'EOF'
#!/bin/bash
# Healthcare API monitoring script

LOG_FILE="/var/log/healthcare-api/monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Check API service
if systemctl is-active --quiet healthcare-api; then
    echo "[$DATE] API service: RUNNING" >> $LOG_FILE
else
    echo "[$DATE] API service: STOPPED" >> $LOG_FILE
    systemctl restart healthcare-api
fi

# Check Celery worker
if systemctl is-active --quiet healthcare-celery; then
    echo "[$DATE] Celery worker: RUNNING" >> $LOG_FILE
else
    echo "[$DATE] Celery worker: STOPPED" >> $LOG_FILE
    systemctl restart healthcare-celery
fi

# Check database connection
if pg_isready -h localhost -p 5432 -U healthcare_user; then
    echo "[$DATE] Database: CONNECTED" >> $LOG_FILE
else
    echo "[$DATE] Database: DISCONNECTED" >> $LOG_FILE
fi

# Check Redis connection
if redis-cli ping | grep -q PONG; then
    echo "[$DATE] Redis: CONNECTED" >> $LOG_FILE
else
    echo "[$DATE] Redis: DISCONNECTED" >> $LOG_FILE
fi

# Check disk space
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "[$DATE] WARNING: Disk usage is ${DISK_USAGE}%" >> $LOG_FILE
fi

# Check memory usage
MEMORY_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ $MEMORY_USAGE -gt 80 ]; then
    echo "[$DATE] WARNING: Memory usage is ${MEMORY_USAGE}%" >> $LOG_FILE
fi
EOF
    
    chmod +x /usr/local/bin/healthcare-monitor.sh
    
    # Add to crontab
    echo "*/5 * * * * /usr/local/bin/healthcare-monitor.sh" | crontab -
    
    log_success "Monitoring configured"
}

# Setup backup
setup_backup() {
    log_info "Setting up backup..."
    
    # Create backup script
    cat > /usr/local/bin/healthcare-backup.sh << 'EOF'
#!/bin/bash
# Healthcare API backup script

BACKUP_DIR="/opt/backups/healthcare-api"
DATE=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="healthcare_backup_$DATE.sql"

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
pg_dump -h localhost -U healthcare_user healthcare_scheduling > $BACKUP_DIR/$BACKUP_FILE

# Compress backup
gzip $BACKUP_DIR/$BACKUP_FILE

# Remove old backups (keep last 30 days)
find $BACKUP_DIR -name "healthcare_backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE.gz"
EOF
    
    chmod +x /usr/local/bin/healthcare-backup.sh
    
    # Add to crontab (daily at 2 AM)
    echo "0 2 * * * /usr/local/bin/healthcare-backup.sh" | crontab -
    
    log_success "Backup configured"
}

# Start services
start_services() {
    log_info "Starting services..."
    
    # Start services
    systemctl start healthcare-api
    systemctl start healthcare-celery
    systemctl start healthcare-celery-beat
    
    # Wait for services to start
    sleep 10
    
    # Check service status
    if systemctl is-active --quiet healthcare-api; then
        log_success "API service started"
    else
        log_error "Failed to start API service"
        systemctl status healthcare-api
    fi
    
    if systemctl is-active --quiet healthcare-celery; then
        log_success "Celery worker started"
    else
        log_error "Failed to start Celery worker"
        systemctl status healthcare-celery
    fi
}

# Main deployment function
main() {
    log_info "Starting Healthcare API deployment..."
    
    check_root
    create_user
    install_dependencies
    setup_app_directory
    deploy_application
    setup_database
    configure_redis
    setup_services
    configure_nginx
    configure_firewall
    setup_monitoring
    setup_backup
    start_services
    
    log_success "Deployment completed successfully!"
    log_info "API should be available at: http://your-domain.com"
    log_info "Check service status with: systemctl status healthcare-api"
    log_info "View logs with: journalctl -u healthcare-api -f"
}

# Run main function
main "$@"
