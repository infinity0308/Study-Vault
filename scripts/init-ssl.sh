#!/usr/bin/env bash
set -e

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "=========================================================="
    echo " StudyVault SSL Initialization Script (Certbot + HTTPS)"
    echo "=========================================================="
    echo "Usage:   ./scripts/init-ssl.sh <domain_name> <email_address>"
    echo "Example: ./scripts/init-ssl.sh studyvault.yourdomain.com admin@yourdomain.com"
    echo ""
    echo "Prerequisites:"
    echo " 1. Your domain's DNS A record must point to this server's Public IP."
    echo " 2. AWS Security Group must allow Inbound Port 80 (HTTP) and Port 443 (HTTPS)."
    echo "=========================================================="
    exit 1
fi

DOMAIN="$1"
EMAIL="$2"
DATA_PATH="./certbot"

echo "==> Configuring HTTPS for $DOMAIN ($EMAIL)..."

# Ensure directories exist
mkdir -p "$DATA_PATH/conf/live/$DOMAIN"
mkdir -p "$DATA_PATH/www"

# 1. Create temporary dummy self-signed certificate so Nginx can start if no cert exists
if [ ! -f "$DATA_PATH/conf/live/$DOMAIN/fullchain.pem" ]; then
    echo "==> Generating temporary self-signed certificate for initial Nginx boot..."
    if command -v openssl >/dev/null 2>&1; then
        openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
            -keyout "$DATA_PATH/conf/live/$DOMAIN/privkey.pem" \
            -out "$DATA_PATH/conf/live/$DOMAIN/fullchain.pem" \
            -subj "/CN=localhost" >/dev/null 2>&1
    else
        docker run --rm -v "$(pwd)/$DATA_PATH/conf/live/$DOMAIN:/out" alpine/openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
            -keyout /out/privkey.pem \
            -out /out/fullchain.pem \
            -subj "/CN=localhost" >/dev/null 2>&1
    fi
fi

# 2. Write Nginx HTTPS configuration
echo "==> Writing Nginx HTTPS configuration..."
cat <<EOF > ./nginx/conf.d/default.conf
upstream web_upstream {
    server web:8000;
}

# HTTP: Let's Encrypt challenge & HTTPS redirect
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 25M;

    # ACME challenge for Certbot
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirect all HTTP to HTTPS
    location / {
        return 301 https://\$host\$request_uri;
    }
}

# HTTPS: Production SSL configuration
server {
    listen 443 ssl;
    server_name $DOMAIN;

    client_max_body_size 25M;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;

    # Security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Static files served directly by Nginx
    location /static/ {
        alias /var/www/static/;
        expires 30d;
        access_log off;
        add_header Cache-Control "public, max-age=2592000, immutable";
    }

    # Proxy dynamic requests to Django Gunicorn
    location / {
        proxy_pass http://web_upstream;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
        proxy_send_timeout 60s;
    }
}
EOF

# 3. Boot/Reload Nginx so it serves port 80 and the challenge directory
echo "==> Starting / Reloading Nginx container..."
docker compose up -d nginx

# 4. Remove dummy cert so Certbot can place the genuine certificate
echo "==> Cleaning temporary placeholder certificate..."
rm -rf "$DATA_PATH/conf/live/$DOMAIN"

# 5. Request official Let's Encrypt Certificate
echo "==> Requesting official Let's Encrypt certificate..."
docker compose run --rm certbot certonly --webroot -w /var/www/certbot \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --rsa-key-size 4096 \
    --agree-tos \
    --force-renewal \
    --non-interactive

# 6. Reload Nginx to activate the verified certificate
echo "==> Reloading Nginx with active SSL certificate..."
docker compose exec nginx nginx -s reload

# 7. Start the automatic renewal background container
echo "==> Starting Certbot auto-renewal daemon..."
docker compose up -d certbot

echo ""
echo "=========================================================="
echo " SUCCESS! HTTPS is now active at: https://$DOMAIN"
echo " Certificates will auto-renew every 12 hours via Certbot."
echo "=========================================================="
