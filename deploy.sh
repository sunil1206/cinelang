#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CineLang — Production Deployment Script
# Domain : cinelang.linuslearning.in
# Server : Ubuntu 22.04 (tested), must be run as root or via sudo
#
# Usage:
#   sudo bash deploy.sh                       # interactive first-time setup
#   sudo bash deploy.sh --update              # pull latest code & rebuild
#   sudo bash deploy.sh --email you@mail.com  # set certbot email non-interactively
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="cinelang.linuslearning.in"
APP_DIR="/opt/cinelang"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
NGINX_CONF="/etc/nginx/sites-available/cinelang"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Parse flags ───────────────────────────────────────────────────────────────
UPDATE_ONLY=false
CERTBOT_EMAIL=""
for arg in "$@"; do
  case $arg in
    --update)   UPDATE_ONLY=true ;;
    --email=*)  CERTBOT_EMAIL="${arg#*=}" ;;
    --email)    shift; CERTBOT_EMAIL="$1" ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
info()    { echo -e "\e[36m[INFO]\e[0m  $*"; }
success() { echo -e "\e[32m[OK]\e[0m    $*"; }
warn()    { echo -e "\e[33m[WARN]\e[0m  $*"; }
die()     { echo -e "\e[31m[ERR]\e[0m   $*" >&2; exit 1; }

require_root() {
  [ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash deploy.sh"
}

prompt() {
  local var="$1" prompt_text="$2" default="${3:-}"
  if [ -n "${!var:-}" ]; then return; fi
  if [ -n "$default" ]; then
    read -rp "$prompt_text [$default]: " val
    eval "$var=\"${val:-$default}\""
  else
    read -rp "$prompt_text: " val
    [ -n "$val" ] || die "$var is required"
    eval "$var=\"$val\""
  fi
}

# ── 1. Root check ─────────────────────────────────────────────────────────────
require_root

# ── 2. System packages ────────────────────────────────────────────────────────
info "Checking system packages..."
apt-get update -qq

install_if_missing() {
  dpkg -l "$1" &>/dev/null || { info "Installing $1..."; apt-get install -y -qq "$1"; }
}
install_if_missing curl
install_if_missing git
install_if_missing nginx
install_if_missing certbot
install_if_missing python3-certbot-nginx

# ── 3. Docker ─────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  info "Installing Docker..."
  curl -fsSL https://get.docker.com | bash
  systemctl enable --now docker
  success "Docker installed"
fi

if ! docker compose version &>/dev/null && ! docker-compose version &>/dev/null; then
  info "Installing Docker Compose plugin..."
  apt-get install -y -qq docker-compose-plugin
fi

# Compose command (newer installations use `docker compose`, older use `docker-compose`)
if docker compose version &>/dev/null 2>&1; then
  COMPOSE="docker compose"
else
  COMPOSE="docker-compose"
fi
success "Docker ready ($COMPOSE)"

# ── 4. App directory ──────────────────────────────────────────────────────────
info "Setting up app directory at $APP_DIR..."
mkdir -p "$BACKEND_DIR" "$FRONTEND_DIR"

# Copy source from where the script lives (repo root assumed to be $SCRIPT_DIR)
info "Copying backend source..."
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' --exclude='cinelang.db' \
  "$SCRIPT_DIR/" "$BACKEND_DIR/"

info "Copying frontend source..."
FRONTEND_SRC="$(dirname "$SCRIPT_DIR")/cinelang-next"
if [ -d "$FRONTEND_SRC" ]; then
  rsync -a --exclude='node_modules' --exclude='.next' --exclude='.env.local' \
    "$FRONTEND_SRC/" "$FRONTEND_DIR/"
else
  die "Frontend source not found at $FRONTEND_SRC — clone cinelang-next alongside cinelang."
fi

# ── 5. Environment file ───────────────────────────────────────────────────────
ENV_FILE="$BACKEND_DIR/.env"
if [ "$UPDATE_ONLY" = false ] && [ ! -f "$ENV_FILE" ]; then
  info "Creating .env (you will need your API keys)..."

  prompt GOOGLE_CLIENT_ID     "Google Client ID"
  prompt GOOGLE_CLIENT_SECRET "Google Client Secret"
  prompt GEMINI_API_KEY       "Gemini API key"
  prompt OPENSUBS_API_KEY     "OpenSubtitles API key (press Enter to skip)" ""
  JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  NEXTAUTH_SECRET=$(openssl rand -base64 32 | tr -d '\n')

  cat > "$ENV_FILE" <<EOF
NEXTAUTH_URL=https://${DOMAIN}
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
GEMINI_API_KEY=${GEMINI_API_KEY}
OPENSUBS_API_KEY=${OPENSUBS_API_KEY}
JWT_SECRET=${JWT_SECRET}
NEXTAUTH_SECRET=${NEXTAUTH_SECRET}
EOF
  chmod 600 "$ENV_FILE"
  success ".env written to $ENV_FILE"
elif [ -f "$ENV_FILE" ]; then
  success ".env already exists — skipping (delete $ENV_FILE to re-run setup)"
fi

# ── 6. Build & start Docker ───────────────────────────────────────────────────
info "Building and starting containers..."
cd "$BACKEND_DIR"

# Update docker-compose frontend context to absolute path inside APP_DIR
# (The compose file references ../cinelang-next which works from repo but not /opt)
sed -i "s|context: \.\./cinelang-next|context: $FRONTEND_DIR|g" docker-compose.yml

$COMPOSE pull --quiet || true
$COMPOSE build --no-cache
$COMPOSE up -d --remove-orphans
success "Containers started"

# ── 7. Nginx configuration ────────────────────────────────────────────────────
info "Configuring Nginx..."

# Step 7a: Install HTTP-only config first so certbot ACME challenge can work
cat > "$NGINX_CONF" <<'NGINX_HTTP'
server {
    listen 80;
    listen [::]:80;
    server_name cinelang.linuslearning.in;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}
NGINX_HTTP

mkdir -p /var/www/certbot
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/cinelang 2>/dev/null || true
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t && systemctl reload nginx
success "Nginx HTTP config active"

# ── 8. SSL certificate ────────────────────────────────────────────────────────
CERT_PATH="/etc/letsencrypt/live/$DOMAIN"
if [ ! -d "$CERT_PATH" ]; then
  info "Obtaining Let's Encrypt certificate for $DOMAIN..."
  if [ -z "$CERTBOT_EMAIL" ]; then
    prompt CERTBOT_EMAIL "Email for Let's Encrypt notifications (e.g. admin@linuslearning.in)"
  fi
  certbot certonly \
    --nginx \
    --non-interactive \
    --agree-tos \
    --email "$CERTBOT_EMAIL" \
    --domains "$DOMAIN" \
    --redirect
  success "SSL certificate obtained"
else
  success "SSL certificate already present — skipping certbot"
fi

# ── 9. Full HTTPS Nginx config ────────────────────────────────────────────────
info "Writing HTTPS Nginx config..."
cp "$BACKEND_DIR/nginx/cinelang.conf" "$NGINX_CONF"
nginx -t && systemctl reload nginx
success "Nginx HTTPS config active"

# ── 10. Certbot auto-renewal cron ────────────────────────────────────────────
CRON_LINE="0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'"
( crontab -l 2>/dev/null | grep -v certbot; echo "$CRON_LINE" ) | crontab -
success "Certbot renewal cron installed (daily at 03:00)"

# ── 11. Systemd service (optional: auto-start on reboot) ─────────────────────
SERVICE_FILE="/etc/systemd/system/cinelang.service"
if [ ! -f "$SERVICE_FILE" ]; then
  info "Creating systemd service..."
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=CineLang Docker Compose
Requires=docker.service
After=docker.service network.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$BACKEND_DIR
ExecStart=/usr/bin/docker compose up -d --remove-orphans
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable cinelang.service
  success "Systemd service enabled (auto-start on reboot)"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
success "CineLang deployed!"
echo ""
echo "  URL      : https://$DOMAIN"
echo "  API docs : https://$DOMAIN/docs"
echo "  Logs     : cd $BACKEND_DIR && $COMPOSE logs -f"
echo "  Update   : sudo bash $SCRIPT_DIR/deploy.sh --update"
echo ""
echo "  Google OAuth redirect URI to add in Google Cloud Console:"
echo "  https://$DOMAIN/api/auth/callback/google"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
