#!/bin/bash

#############################################
# NetVault - Network Device Backup System
# Installation Script
# Version: 1.0
#############################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="/opt/netvault"
CURRENT_DIR=$(pwd)

# Print colored message
print_message() {
    local color=$1
    shift
    echo -e "${color}$@${NC}"
}

print_header() {
    echo ""
    print_message "$BLUE" "================================================"
    print_message "$BLUE" "$1"
    print_message "$BLUE" "================================================"
}

print_success() {
    print_message "$GREEN" "✓ $1"
}

print_error() {
    print_message "$RED" "✗ $1"
}

print_warning() {
    print_message "$YELLOW" "⚠ $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        echo "Please run: sudo ./install.sh"
        exit 1
    fi
}

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        print_error "Cannot detect OS"
        exit 1
    fi

    print_success "Detected OS: $OS $VER"
}

# Install dependencies
install_dependencies() {
    print_header "Installing System Dependencies"

    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        apt-get update
        apt-get install -y \
            python3 \
            python3-pip \
            python3-venv \
            python3-dev \
            nginx \
            redis-server \
            mariadb-server \
            libmariadb-dev \
            build-essential \
            pkg-config \
            git \
            curl \
            software-properties-common \
            libldap2-dev \
            libsasl2-dev \
            libssl-dev

        # Enable and start services
        systemctl enable redis-server
        systemctl start redis-server
        systemctl enable mariadb
        systemctl start mariadb

        print_success "Dependencies installed"
    fi
}

# Setup Redis password
setup_redis_password() {
    print_header "Securing Redis"

    # Generate random password for Redis
    REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)

    # Configure Redis password
    if [ -f /etc/redis/redis.conf ]; then
        # Remove existing requirepass if any
        sed -i '/^requirepass /d' /etc/redis/redis.conf
        # Add new password
        echo "requirepass ${REDIS_PASSWORD}" >> /etc/redis/redis.conf

        # Disable protected-mode since we use password
        sed -i 's/^protected-mode yes/protected-mode no/' /etc/redis/redis.conf

        # Bind only to localhost
        sed -i 's/^bind .*/bind 127.0.0.1/' /etc/redis/redis.conf

        # Restart Redis
        systemctl restart redis-server

        print_success "Redis secured with password"
    else
        print_warning "Redis config not found, skipping password setup"
        REDIS_PASSWORD=""
    fi
}

# Gather installation settings
gather_settings() {
    print_header "NetVault Installation Configuration"

    echo ""
    echo "Please provide the following information:"
    echo ""

    # Domain or IP
    read -p "Enter domain name or IP address [localhost]: " DOMAIN
    DOMAIN=${DOMAIN:-localhost}

    # Protocol selection
    echo ""
    echo "Choose protocol:"
    echo "1) HTTP (port 80) - Development/Testing"
    echo "2) HTTPS (port 443) - Production (recommended)"
    read -p "Select option [1]: " PROTOCOL_CHOICE
    PROTOCOL_CHOICE=${PROTOCOL_CHOICE:-1}

    if [[ "$PROTOCOL_CHOICE" == "2" ]]; then
        USE_HTTPS="true"
        PORT=443

        echo ""
        echo "HTTPS Certificate options:"
        echo "1) Let's Encrypt (automatic, free)"
        echo "2) Custom certificate (provide paths)"
        echo "3) Self-signed certificate (for testing)"
        read -p "Select option [1]: " CERT_CHOICE
        CERT_CHOICE=${CERT_CHOICE:-1}

        if [[ "$CERT_CHOICE" == "2" ]]; then
            read -p "Path to SSL certificate: " SSL_CERT_PATH
            read -p "Path to SSL certificate key: " SSL_KEY_PATH
        fi
    else
        USE_HTTPS="false"
        PORT=80
    fi

    # Database settings
    echo ""
    print_message "$BLUE" "Database Configuration"
    read -p "Database name [netvault]: " DB_NAME
    DB_NAME=${DB_NAME:-netvault}

    read -p "Database user [netvault_user]: " DB_USER
    DB_USER=${DB_USER:-netvault_user}

    read -sp "Database password: " DB_PASS
    echo ""

    # Admin user
    echo ""
    print_message "$BLUE" "Administrator Account"
    read -p "Admin username [admin]: " ADMIN_USER
    ADMIN_USER=${ADMIN_USER:-admin}

    read -p "Admin email: " ADMIN_EMAIL

    read -sp "Admin password: " ADMIN_PASS
    echo ""
    read -sp "Confirm admin password: " ADMIN_PASS_CONFIRM
    echo ""

    if [[ "$ADMIN_PASS" != "$ADMIN_PASS_CONFIRM" ]]; then
        print_error "Passwords do not match"
        exit 1
    fi

    # Admin panel IP restriction
    echo ""
    print_message "$BLUE" "Admin Panel Security"
    echo "Restrict /admin/ access to specific IP addresses? (recommended for production)"
    read -p "Enable IP whitelist for /admin/? [Y/n]: " RESTRICT_ADMIN
    RESTRICT_ADMIN=${RESTRICT_ADMIN:-Y}

    if [[ "$RESTRICT_ADMIN" =~ ^[Yy]$ ]]; then
        echo ""
        echo "Enter trusted IP addresses (one per line, empty line to finish):"
        echo "Example: 192.168.1.100, 10.0.0.5, your office IP"
        ADMIN_ALLOWED_IPS=()
        while true; do
            read -p "IP address: " ip
            if [[ -z "$ip" ]]; then
                break
            fi
            ADMIN_ALLOWED_IPS+=("$ip")
            print_success "Added: $ip"
        done

        if [[ ${#ADMIN_ALLOWED_IPS[@]} -eq 0 ]]; then
            print_warning "No IPs specified, admin panel will be accessible from anywhere"
            RESTRICT_ADMIN="n"
        else
            print_success "${#ADMIN_ALLOWED_IPS[@]} IP(s) whitelisted for /admin/"
        fi
    fi

    echo ""
    print_success "Configuration collected"
}

# Generate encryption key
generate_encryption_key() {
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
}

# Generate Django secret key
generate_secret_key() {
    python3 -c "import random, string; print(''.join(random.SystemRandom().choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(50)))"
}

# Setup database
setup_database() {
    print_header "Configuring MariaDB Database"

    # Create database and user
    mysql -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    mysql -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';"
    mysql -e "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';"
    mysql -e "FLUSH PRIVILEGES;"

    print_success "Database configured"
}

# Build frontend if needed
build_frontend() {
    if [ ! -d "$CURRENT_DIR/frontend/build" ]; then
        print_header "Building Frontend (React)"

        # Install Node.js 20 if not present or if version < 20
        node_version=$(node -v 2>/dev/null | cut -d'v' -f2 | cut -d'.' -f1)
        if [ -z "$node_version" ] || [ "$node_version" -lt 20 ]; then
            print_message "$BLUE" "Installing Node.js 20..."
            curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
            apt-get install -y nodejs
        fi

        cd $CURRENT_DIR/frontend

        # Install dependencies
        print_message "$BLUE" "Installing npm dependencies..."
        npm install

        # Build production
        print_message "$BLUE" "Building production bundle..."
        npm run build

        cd $CURRENT_DIR
        print_success "Frontend built successfully"
    else
        print_success "Frontend build already exists"
    fi
}

# Install NetVault application
install_application() {
    print_header "Installing NetVault Application"

    # Build frontend first if needed
    build_frontend

    # Create installation directory
    mkdir -p $INSTALL_DIR

    # Copy backend
    cp -r $CURRENT_DIR/backend/* $INSTALL_DIR/

    # Copy frontend build (separate from Django staticfiles)
    mkdir -p $INSTALL_DIR/frontend_build
    cp -r $CURRENT_DIR/frontend/build/* $INSTALL_DIR/frontend_build/

    # Create required directories
    mkdir -p $INSTALL_DIR/logs
    mkdir -p $INSTALL_DIR/media
    mkdir -p $INSTALL_DIR/staticfiles

    # Set permissions
    chown -R www-data:www-data $INSTALL_DIR
    chmod -R 755 $INSTALL_DIR

    print_success "Application files installed"
}

# Setup Python environment
setup_python_env() {
    print_header "Setting Up Python Environment"

    cd $INSTALL_DIR

    # Create virtual environment
    python3 -m venv venv

    # Install Python dependencies
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt

    print_success "Python environment configured"
}

# Generate .env file
generate_env_file() {
    print_header "Generating Configuration File"

    ENCRYPTION_KEY=$(generate_encryption_key)
    SECRET_KEY=$(generate_secret_key)

    cat > $INSTALL_DIR/.env <<EOF
# NetVault Configuration
# Generated on $(date)

# Django Settings
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=${DOMAIN},localhost,127.0.0.1
# CORS: private IPs auto-allowed via regex, add public domains here if needed
CORS_ALLOWED_ORIGINS=http://${DOMAIN},https://${DOMAIN}

# Database Configuration
DB_ENGINE=mysql
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASS}
DB_HOST=localhost
DB_PORT=3306

# Encryption
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# Redis
REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0

# Email Configuration (configure later)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=

# Telegram (configure later)
TELEGRAM_ENABLED=False
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# LDAP (configure later)
LDAP_ENABLED=False
LDAP_SERVER_URI=
LDAP_BIND_DN=
LDAP_BIND_PASSWORD=
LDAP_USER_SEARCH_BASE=

# Backup Settings
BACKUP_RETENTION_DAYS=90
BACKUP_PARALLEL_WORKERS=5

# Device Check Settings (Hybrid mode: TCP + SSH fallback)
DEVICE_CHECK_INTERVAL_MINUTES=5
DEVICE_CHECK_TCP_TIMEOUT=2
DEVICE_CHECK_SSH_TIMEOUT=5

# JWT Settings
JWT_ACCESS_TOKEN_LIFETIME=60
JWT_REFRESH_TOKEN_LIFETIME=1440

# Security Settings
# USE_HTTPS: Enable HTTPS mode (secure cookies, HSTS headers)
# SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE: Cookies only sent over HTTPS
# SECURE_SSL_REDIRECT is NOT used - Nginx handles HTTP->HTTPS redirects
USE_HTTPS=$([ "$USE_HTTPS" == "true" ] && echo "True" || echo "False")
SESSION_COOKIE_SECURE=$([ "$USE_HTTPS" == "true" ] && echo "True" || echo "False")
CSRF_COOKIE_SECURE=$([ "$USE_HTTPS" == "true" ] && echo "True" || echo "False")

# Registration Control (disabled by default for security)
ALLOW_PUBLIC_REGISTRATION=False
EOF

    chmod 600 $INSTALL_DIR/.env
    chown www-data:www-data $INSTALL_DIR/.env

    print_success "Configuration file created"
}

# Run Django migrations
run_migrations() {
    print_header "Running Database Migrations"

    cd $INSTALL_DIR
    ./venv/bin/python manage.py makemigrations
    ./venv/bin/python manage.py migrate
    ./venv/bin/python manage.py collectstatic --noinput

    print_success "Database migrations completed"

    # Add popular network device vendors
    print_message "$BLUE" "Adding popular network device vendors..."
    ./venv/bin/python manage.py add_popular_vendors
    print_success "Vendors added"

    # Add popular device types
    print_message "$BLUE" "Adding popular device types..."
    ./venv/bin/python manage.py add_popular_device_types
    print_success "Device types added"
}

# Create admin user
create_admin() {
    print_header "Creating Administrator Account"

    cd $INSTALL_DIR
    # Use environment variables to avoid password exposure in process list
    NETVAULT_ADMIN_USER="${ADMIN_USER}" \
    NETVAULT_ADMIN_EMAIL="${ADMIN_EMAIL}" \
    NETVAULT_ADMIN_PASS="${ADMIN_PASS}" \
    ./venv/bin/python manage.py shell <<'EOF'
import os
from accounts.models import User
username = os.environ.get('NETVAULT_ADMIN_USER')
email = os.environ.get('NETVAULT_ADMIN_EMAIL')
password = os.environ.get('NETVAULT_ADMIN_PASS')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password,
        role='administrator'
    )
    print('Admin user created')
else:
    print('Admin user already exists')
EOF

    print_success "Administrator account created"
}

# Finalize permissions
finalize_permissions() {
    print_header "Finalizing Permissions"

    # Fix ownership of all files (migrations and admin creation may have created files as root)
    chown -R www-data:www-data ${INSTALL_DIR}

    # Ensure .env is secure
    chmod 600 ${INSTALL_DIR}/.env

    # Ensure logs directory is writable
    chmod 755 ${INSTALL_DIR}/logs

    # Ensure media directory is writable
    chmod 755 ${INSTALL_DIR}/media

    print_success "Permissions finalized"
}

# Setup systemd services
setup_systemd_services() {
    print_header "Configuring Systemd Services"

    # Backend service (Daphne)
    cat > /etc/systemd/system/netvault-backend.service <<EOF
[Unit]
Description=NetVault Django Backend (ASGI with Daphne)
After=network.target redis.service mariadb.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${INSTALL_DIR}/venv/bin"
ExecStart=${INSTALL_DIR}/venv/bin/daphne -b 0.0.0.0 -p 8000 netvault.asgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Celery Worker service
    cat > /etc/systemd/system/netvault-celery-worker.service <<EOF
[Unit]
Description=NetVault Celery Worker
After=network.target redis.service mariadb.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${INSTALL_DIR}/venv/bin"
ExecStart=${INSTALL_DIR}/venv/bin/celery -A netvault worker --loglevel=info --concurrency=10
ExecStop=/bin/kill -TERM \$MAINPID
TimeoutStopSec=300
KillMode=mixed
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Celery Beat service
    cat > /etc/systemd/system/netvault-celery-beat.service <<EOF
[Unit]
Description=NetVault Celery Beat (Scheduler)
After=network.target redis.service mariadb.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${INSTALL_DIR}/venv/bin"
ExecStart=${INSTALL_DIR}/venv/bin/celery -A netvault beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
ExecStop=/bin/kill -TERM \$MAINPID
TimeoutStopSec=30
KillMode=mixed
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload

    # Enable and start services
    systemctl enable netvault-backend.service
    systemctl enable netvault-celery-worker.service
    systemctl enable netvault-celery-beat.service

    systemctl start netvault-backend.service
    systemctl start netvault-celery-worker.service
    systemctl start netvault-celery-beat.service

    print_success "Systemd services configured and started"
}

# Setup SSL certificate
setup_ssl_certificate() {
    if [[ "$USE_HTTPS" == "true" ]]; then
        print_header "Configuring SSL Certificate"

        if [[ "$CERT_CHOICE" == "1" ]]; then
            # Let's Encrypt
            print_message "$BLUE" "Installing Certbot for Let's Encrypt..."

            apt-get install -y certbot python3-certbot-nginx

            # Stop nginx temporarily
            systemctl stop nginx 2>/dev/null || true

            # Get certificate
            certbot certonly --standalone -d $DOMAIN --non-interactive --agree-tos -m $ADMIN_EMAIL

            SSL_CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
            SSL_KEY_PATH="/etc/letsencrypt/live/$DOMAIN/privkey.pem"

            print_success "Let's Encrypt certificate obtained"

        elif [[ "$CERT_CHOICE" == "3" ]]; then
            # Self-signed certificate
            print_message "$BLUE" "Generating self-signed certificate..."

            mkdir -p /etc/nginx/ssl
            openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
                -keyout /etc/nginx/ssl/netvault.key \
                -out /etc/nginx/ssl/netvault.crt \
                -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"

            SSL_CERT_PATH="/etc/nginx/ssl/netvault.crt"
            SSL_KEY_PATH="/etc/nginx/ssl/netvault.key"

            print_warning "Self-signed certificate created (not recommended for production)"
        fi
    fi
}

# Generate IP whitelist directives for Nginx
generate_admin_ip_whitelist() {
    if [[ "$RESTRICT_ADMIN" =~ ^[Yy]$ ]] && [[ ${#ADMIN_ALLOWED_IPS[@]} -gt 0 ]]; then
        for ip in "${ADMIN_ALLOWED_IPS[@]}"; do
            echo "        allow $ip;"
        done
        echo "        deny all;"
        echo ""
    fi
}

# Setup nginx
setup_nginx() {
    print_header "Configuring Nginx"

    if [[ "$USE_HTTPS" == "true" ]]; then
        # HTTPS configuration
        cat > /etc/nginx/sites-available/netvault <<EOF
# HTTP redirect to HTTPS
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$server_name\$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    # SSL configuration
    ssl_certificate ${SSL_CERT_PATH};
    ssl_certificate_key ${SSL_KEY_PATH};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    client_max_body_size 100M;

    # React Frontend - serve from frontend_build
    root ${INSTALL_DIR}/frontend_build;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml+rss;

    # Django API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 120s;
        proxy_read_timeout 120s;
    }

    # Django admin (IP restricted for security)
    location /admin/ {
$(generate_admin_ip_whitelist)        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Django static files (admin CSS/JS)
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
    }

    # Media files
    location /media/ {
        alias ${INSTALL_DIR}/media/;
        expires 7d;
    }

    # WebSocket for real-time logs
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }

    # Frontend routes (React Router)
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)\$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
EOF
    else
        # HTTP configuration
        cat > /etc/nginx/sites-available/netvault <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 100M;

    # React Frontend - serve from frontend_build
    root ${INSTALL_DIR}/frontend_build;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml+rss;

    # Django API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 120s;
        proxy_read_timeout 120s;
    }

    # Django admin (IP restricted for security)
    location /admin/ {
$(generate_admin_ip_whitelist)        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Django static files (admin CSS/JS)
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
    }

    # Media files
    location /media/ {
        alias ${INSTALL_DIR}/media/;
        expires 7d;
    }

    # WebSocket for real-time logs
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }

    # Frontend routes (React Router)
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)\$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
EOF
    fi

    # Enable site
    ln -sf /etc/nginx/sites-available/netvault /etc/nginx/sites-enabled/

    # Remove default site
    rm -f /etc/nginx/sites-enabled/default

    # Test nginx configuration
    nginx -t

    # Restart nginx
    systemctl enable nginx
    systemctl restart nginx

    print_success "Nginx configured and started"
}

# Setup firewall
setup_firewall() {
    print_header "Configuring Firewall"

    if command -v ufw &> /dev/null; then
        ufw --force enable

        if [[ "$USE_HTTPS" == "true" ]]; then
            ufw allow 443/tcp
            ufw allow 80/tcp  # For redirect
        else
            ufw allow 80/tcp
        fi

        ufw allow 22/tcp  # SSH

        print_success "Firewall configured"
    else
        print_warning "UFW not found, skipping firewall configuration"
    fi
}

# Print installation summary
print_summary() {
    print_header "Installation Complete!"

    echo ""
    print_message "$GREEN" "NetVault has been successfully installed!"
    echo ""
    echo "Access Information:"
    echo "===================="

    if [[ "$USE_HTTPS" == "true" ]]; then
        echo "URL: https://${DOMAIN}"
    else
        echo "URL: http://${DOMAIN}"
    fi

    echo ""
    echo "Admin Credentials:"
    echo "  Username: ${ADMIN_USER}"
    echo "  Email: ${ADMIN_EMAIL}"
    echo "  Password: [as provided during installation]"
    echo ""
    echo "Installation Directory: ${INSTALL_DIR}"
    echo ""
    echo "Services:"
    echo "  - netvault-backend.service (Django/Daphne)"
    echo "  - netvault-celery-worker.service (Task queue)"
    echo "  - netvault-celery-beat.service (Scheduler)"
    echo ""
    echo "Management Commands:"
    echo "  View logs: journalctl -u netvault-backend -f"
    echo "  Restart: systemctl restart netvault-backend"
    echo "  Status: systemctl status netvault-backend"
    echo ""
    echo "Configuration file: ${INSTALL_DIR}/.env"
    echo ""

    if [[ "$USE_HTTPS" == "true" ]] && [[ "$CERT_CHOICE" == "1" ]]; then
        echo "SSL Certificate:"
        echo "  Let's Encrypt certificate will auto-renew"
        echo "  Manual renewal: certbot renew"
        echo ""
    fi

    if [[ "$RESTRICT_ADMIN" =~ ^[Yy]$ ]] && [[ ${#ADMIN_ALLOWED_IPS[@]} -gt 0 ]]; then
        echo "Admin Panel Access:"
        echo "  Access restricted to whitelisted IPs:"
        for ip in "${ADMIN_ALLOWED_IPS[@]}"; do
            echo "    - $ip"
        done
        echo "  To modify: edit /etc/nginx/sites-available/netvault"
        echo ""
    fi

    print_message "$YELLOW" "IMPORTANT:"
    echo "  1. Configure email settings in ${INSTALL_DIR}/.env"
    echo "  2. Configure Telegram notifications (optional)"
    echo "  3. After changing settings, restart services:"
    echo "     systemctl restart netvault-backend netvault-celery-*"
    echo ""

    print_message "$GREEN" "Thank you for installing NetVault!"
    echo ""
}

# Main installation flow
main() {
    print_header "NetVault Installation"
    echo "Network Device Configuration Backup System"
    echo ""

    check_root
    detect_os
    gather_settings

    echo ""
    read -p "Proceed with installation? [Y/n]: " CONFIRM
    CONFIRM=${CONFIRM:-Y}

    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        print_error "Installation cancelled"
        exit 0
    fi

    install_dependencies
    setup_redis_password
    setup_database
    install_application
    setup_python_env
    generate_env_file
    run_migrations
    create_admin
    finalize_permissions
    setup_systemd_services
    setup_ssl_certificate
    setup_nginx
    setup_firewall

    print_summary
}

# Run main installation
main
