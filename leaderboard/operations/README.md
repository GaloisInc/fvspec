# Operations Directory Overview

This infrastructure documentation describes the deployment setup for the fvspec leaderboard website.

## Architecture Overview

The fvspec leaderboard uses a three-service architecture:

1. **Frontend (packages/web)**: Next.js static site served via nginx
2. **API (packages/api)**: Hono REST API running on port 3001
3. **Worker (packages/worker)**: Background job processor

This operations directory focuses on the **frontend nginx configuration** as the single source of truth for web server setup.

## Key Configuration Files

### nginx-leaderboard.conf

The **nginx-leaderboard.conf** handles:

- Static site serving from `/home/[user]/fvspec-leaderboard/out/` (Next.js static export)
- Reverse proxy to API backend on port 3001
- HTTPS enforcement with automatic HTTP→HTTPS redirects
- Aggressive caching for static assets (1-year expiration)
- CORS headers for cross-origin requests
- Client-side routing support (SPA-friendly)

### nginx-api.conf (Optional)

If you want to run the API on a separate subdomain or port with nginx as a reverse proxy, use **nginx-api.conf**. This is optional if your API runs directly on a port behind a firewall.

## Installation

### Prerequisites

- Ubuntu/Debian server with nginx installed
- Server hostname: `ec2-35-95-72-128.us-west-2.compute.amazonaws.com` (prototype)
- Existing monorepo clone at `/home/quinnd/fvspec/`
- SSL certificate (via certbot or manual, optional for prototype)
- Built Next.js static site in `packages/web/out/`

### Step 1: Build the Frontend

On your local machine or CI:

```bash
cd leaderboard/packages/web
npm run build  # Generates .next/ directory for SSR, or:
npm run build && npm run export  # For static export to out/
```

**Note**: For static export, you may need to add to `next.config.ts`:

```typescript
const nextConfig: NextConfig = {
  output: 'export', // Enable static export
  // ... other config
}
```

### Step 2: Deploy Files to Server

**Option A: Manual SCP**

```bash
# From your local machine
scp -r leaderboard/packages/web/out/ quinnd@ec2-35-95-72-128.us-west-2.compute.amazonaws.com:/home/quinnd/fvspec/leaderboard/packages/web/

# Or if already on the server, just rebuild in place:
cd /home/quinnd/fvspec/leaderboard/packages/web
git pull
npm run build
```

**Option B: GitHub Actions** (see Deployment Methods below)

### Step 3: Install Nginx Configuration

On the server, symlink the nginx config from the repository (single source of truth):

```bash
# Symlink nginx config from repository to sites-available
sudo ln -sf /home/quinnd/fvspec/leaderboard/operations/nginx-leaderboard.conf \
  /etc/nginx/sites-available/fvspec-leaderboard

# Enable the site by symlinking to sites-enabled
sudo ln -sf /etc/nginx/sites-available/fvspec-leaderboard \
  /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

**Note**: Using symlinks means configuration updates via `git pull` are automatically
reflected after running `nginx -t && systemctl reload nginx`.

### Step 4: Setup SSL with Certbot (Optional for Prototype)

For production with a domain name:

```bash
sudo certbot --nginx -d leaderboard.fvspec.org
```

For the prototype on EC2 (`ec2-35-95-72-128.us-west-2.compute.amazonaws.com`), you can:

- Skip SSL and use HTTP only (simpler for prototyping)
- Or obtain a free SSL certificate for the EC2 hostname using Let's Encrypt
- Or use a custom domain pointed at the EC2 IP and then use certbot

Certbot will automatically modify the nginx configuration to add SSL certificates and HTTPS redirects.

## Deployment Methods

### Automated: GitHub Actions

Create `.github/workflows/deploy-leaderboard.yml`:

```yaml
name: Deploy Leaderboard

on:
  push:
    branches:
      - main
    paths:
      - 'leaderboard/packages/web/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install dependencies
        run: |
          cd leaderboard/packages/web
          npm ci

      - name: Build site
        run: |
          cd leaderboard/packages/web
          npm run build

      - name: Deploy to server
        env:
          SSH_KEY: ${{ secrets.LEADERBOARD_SSH_KEY }}
          SERVER_IP: ${{ secrets.LEADERBOARD_SERVER_IP }}
          SERVER_USER: ${{ secrets.LEADERBOARD_SERVER_USER }}
        run: |
          mkdir -p ~/.ssh
          echo "$SSH_KEY" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          rsync -avz -e "ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=no" \
            leaderboard/packages/web/out/ \
            $SERVER_USER@$SERVER_IP:/home/$SERVER_USER/fvspec/leaderboard/packages/web/out/
```

**Required secrets** (Settings → Secrets → Actions):

- `LEADERBOARD_SSH_KEY`: Private SSH key for server access
- `LEADERBOARD_SERVER_IP`: `ec2-35-95-72-128.us-west-2.compute.amazonaws.com` (or just the IP)
- `LEADERBOARD_SERVER_USER`: `quinnd`

### Manual Deployment

```bash
# 1. Build locally
cd leaderboard/packages/web
npm run build

# 2. Copy to server
scp -r out/ quinnd@ec2-35-95-72-128.us-west-2.compute.amazonaws.com:/home/quinnd/fvspec/leaderboard/packages/web/

# 3. Nginx will automatically serve updated files (no reload needed)
```

**Or deploy directly on the server:**

```bash
# SSH to server
ssh quinnd@ec2-35-95-72-128.us-west-2.compute.amazonaws.com

# Navigate and rebuild
cd /home/quinnd/fvspec/leaderboard/packages/web
git pull
npm install
npm run build

# Nginx automatically serves new files
```

## API Backend Setup

The nginx configuration includes a reverse proxy for the API backend. On the server:

### Install and Run API

```bash
# Navigate to the leaderboard directory
cd /home/quinnd/fvspec/leaderboard
npm install

# Set environment variables
cat > .env <<EOF
DATABASE_URL=postgresql://fvspec_user:your-password@localhost:5432/fvspec
REDIS_URL=redis://localhost:6379
API_TOKEN=$(openssl rand -hex 32)
PORT=3001
NODE_ENV=production
EOF

# Secure the file
chmod 600 .env

# Run API (use systemd service or PM2 for production)
cd packages/api
npm start
```

### Systemd Service for API

Symlink the service file from the repository (single source of truth):

```bash
# Symlink API service
sudo ln -sf /home/quinnd/fvspec/leaderboard/operations/fvspec-api.service \
  /etc/systemd/system/fvspec-api.service

# Reload systemd to pick up the service file
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable fvspec-api
sudo systemctl start fvspec-api
sudo systemctl status fvspec-api
```

The service file is located at `/home/quinnd/fvspec/leaderboard/operations/fvspec-api.service`.

## Worker Backend Setup

The worker runs separately and doesn't need nginx configuration. Symlink the service file:

```bash
# Symlink Worker service
sudo ln -sf /home/quinnd/fvspec/leaderboard/operations/fvspec-worker.service \
  /etc/systemd/system/fvspec-worker.service

# Reload systemd to pick up the service file
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable fvspec-worker
sudo systemctl start fvspec-worker
sudo systemctl status fvspec-worker
```

The service file is located at `/home/quinnd/fvspec/leaderboard/operations/fvspec-worker.service`.

## Configuration Details

### Static Asset Caching

The nginx configuration implements aggressive caching for static assets:

```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

This tells browsers to cache assets for 1 year since Next.js uses content-hash filenames.

### CORS Headers

CORS is enabled for API endpoints:

```nginx
location /api/ {
    add_header 'Access-Control-Allow-Origin' '*';
    add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
    # ... more headers
}
```

### Client-Side Routing

For Next.js App Router, we use:

```nginx
try_files $uri $uri/ /index.html =404;
```

This ensures that client-side routes (e.g., `/leaderboard`, `/submit`) work correctly.

### Security Headers

The configuration includes security headers:

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
```

## Monitoring and Logs

### Nginx Logs

```bash
# Access logs
sudo tail -f /var/log/nginx/access.log

# Error logs
sudo tail -f /var/log/nginx/error.log
```

### API Logs

```bash
# Via journalctl (systemd)
sudo journalctl -u fvspec-api -f

# Or direct logs if using PM2
pm2 logs fvspec-api
```

### Worker Logs

```bash
sudo journalctl -u fvspec-worker -f
```

## Troubleshooting

### 502 Bad Gateway

API backend is not running or not accessible on port 3001:

```bash
# Check if API is running
sudo systemctl status fvspec-api

# Check if port 3001 is listening
sudo netstat -tlnp | grep 3001

# Check API logs
sudo journalctl -u fvspec-api -n 50
```

### 404 on Client-Side Routes

Nginx is not falling back to index.html. Verify `try_files` directive:

```bash
sudo nginx -t
grep -n "try_files" /etc/nginx/sites-available/leaderboard.fvspec.org
```

### SSL Certificate Issues

```bash
# Renew certificates
sudo certbot renew

# Check certificate expiry
sudo certbot certificates
```

### Static Assets Not Updating

Browser cache or CDN cache may be stale:

```bash
# Hard refresh in browser (Ctrl+Shift+R)
# Or clear nginx cache if using proxy_cache
sudo rm -rf /var/cache/nginx/*
sudo systemctl reload nginx
```

## Related Documentation

- **Leaderboard Architecture**: `/leaderboard/AGENTS.md`
- **Frontend Package**: `/leaderboard/packages/web/`
- **API Package**: `/leaderboard/packages/api/`
- **Worker Package**: `/leaderboard/packages/worker/`

## Questions?

Open an issue on GitHub or contact the infrastructure team.
