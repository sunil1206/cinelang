#!/usr/bin/env bash
# CineLang — One-shot server setup
# Run on the server: bash server-setup.sh
set -euo pipefail

DOMAIN="cinelang.linuslearning.in"
APP_DIR="/opt/cinelang"
REPO="https://github.com/sunil1206/cinelang.git"

info()    { echo -e "\033[36m[INFO]\033[0m  $*"; }
success() { echo -e "\033[32m[OK]\033[0m    $*"; }
die()     { echo -e "\033[31m[ERR]\033[0m   $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash server-setup.sh"

# ── 1. System packages ────────────────────────────────────────────────────────
info "Updating packages..."
apt-get update -qq
for pkg in curl git nginx certbot python3-certbot-nginx; do
  dpkg -l "$pkg" &>/dev/null || apt-get install -y -qq "$pkg"
done

# ── 2. Docker ─────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  info "Installing Docker..."
  curl -fsSL https://get.docker.com | bash
  systemctl enable --now docker
fi
if ! docker compose version &>/dev/null 2>&1; then
  apt-get install -y -qq docker-compose-plugin
fi
success "Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

# ── 3. Clone / update repo ────────────────────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
  info "Updating repo..."
  git -C "$APP_DIR" pull --ff-only
else
  info "Cloning repo..."
  git clone "$REPO" "$APP_DIR"
fi

# ── 4. .env file ─────────────────────────────────────────────────────────────
ENV_FILE="$APP_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  info "Creating .env — enter your API keys:"
  read -rp "  GOOGLE_CLIENT_ID: "     GCI;     echo
  read -rp "  GOOGLE_CLIENT_SECRET: " GCS;     echo
  read -rsp "  NEXTAUTH_SECRET (blank = auto-generate): " NS; echo
  read -rp "  GROQ_API_KEY: "         GROQ;    echo
  read -rp "  OPENROUTER_API_KEY: "   OR_KEY;  echo
  read -rp "  GEMINI_API_KEY: "       GEM;     echo
  read -rp "  OPENAI_API_KEY (blank = skip): " OAI; echo
  read -rp "  OPENSUBS_API_KEY (blank = skip): " OPENSUBS; echo
  read -rp "  DEEPL_API_KEY (blank = skip): "   DEEPL;    echo

  JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  [ -z "$NS" ] && NS=$(openssl rand -base64 32 | tr -d '\n')

  cat > "$ENV_FILE" <<EOF
# CineLang production .env
NEXTAUTH_URL=https://${DOMAIN}
NEXTAUTH_SECRET=${NS}
GOOGLE_CLIENT_ID=${GCI}
GOOGLE_CLIENT_SECRET=${GCS}
JWT_SECRET=${JWT_SECRET}

GROQ_API_KEY=${GROQ}
OPENROUTER_API_KEY=${OR_KEY}
GEMINI_API_KEY=${GEM}
OPENAI_API_KEY=${OAI}
DEEPL_API_KEY=${DEEPL}
OPENSUBS_API_KEY=${OPENSUBS}
EOF
  chmod 600 "$ENV_FILE"
  success ".env created"
else
  success ".env already exists — skipping (delete to re-enter keys)"
fi

# ── 5. Build & start containers ───────────────────────────────────────────────
info "Building Docker images (this takes 3-5 min first time)..."
cd "$APP_DIR"
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d --remove-orphans
success "Containers running"

# ── 6. Nginx HTTP config (for certbot) ───────────────────────────────────────
info "Writing Nginx config..."
NGINX_CONF="/etc/nginx/sites-available/cinelang"
cat > "$NGINX_CONF" <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://\$host\$request_uri; }
}
NGINX
mkdir -p /var/www/certbot
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/cinelang
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
success "Nginx HTTP ready"

# ── 7. SSL certificate ────────────────────────────────────────────────────────
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"
if [ ! -d "$CERT_DIR" ]; then
  info "Getting SSL certificate..."
  read -rp "  Email for Let's Encrypt: " LE_EMAIL; echo
  certbot --nginx -n --agree-tos --email "$LE_EMAIL" -d "$DOMAIN"
  success "SSL obtained"
else
  success "SSL already present"
fi

# ── 8. Full HTTPS Nginx config ────────────────────────────────────────────────
cp "$APP_DIR/nginx/cinelang.conf" "$NGINX_CONF"
nginx -t && systemctl reload nginx
success "Nginx HTTPS active"

# ── 9. Auto-renewal cron ──────────────────────────────────────────────────────
(crontab -l 2>/dev/null | grep -v certbot; echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

# ── 10. Systemd auto-start ────────────────────────────────────────────────────
cat > /etc/systemd/system/cinelang.service <<EOF
[Unit]
Description=CineLang
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d --remove-orphans
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=180

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable cinelang.service
success "Auto-start on reboot enabled"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
success "CineLang is live!"
echo ""
echo "  🌐  https://$DOMAIN"
echo "  📖  https://$DOMAIN/docs"
echo "  📋  Logs: docker compose -f $APP_DIR/docker-compose.prod.yml logs -f"
echo "  🔄  Update: git -C $APP_DIR pull && docker compose -f $APP_DIR/docker-compose.prod.yml up -d --build"
echo ""
echo "  Add this to Google Cloud Console → OAuth → Redirect URIs:"
echo "  https://$DOMAIN/api/auth/callback/google"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
