# Deployment Guide

This guide covers deploying the fvspec leaderboard to a production server using nginx.

## Quick Start Checklist

- [ ] Domain name configured (e.g., `leaderboard.fvspec.org`)
- [ ] Server with nginx installed (Ubuntu/Debian recommended)
- [ ] PostgreSQL and Redis running
- [ ] Node.js 20+ and pnpm installed
- [ ] SSL certificate (via certbot)
- [ ] GitHub Actions secrets configured (for automated deployment)

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Internet Traffic                        │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
                         ┌─────────────┐
                         │   Nginx     │ :443 (HTTPS)
                         │  (Reverse   │ :80 (HTTP→HTTPS)
                         │   Proxy)    │
                         └──────┬──────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ Static   │    │   API    │    │  Worker  │
        │  Files   │    │  (Hono)  │    │ (BullMQ) │
        │ (Next.js)│    │  :3001   │    │          │
        └──────────┘    └────┬─────┘    └────┬─────┘
                             │               │
                             └───┬───────────┘
                                 │
                        ┌────────┴────────┐
                        │                 │
                        ▼                 ▼
                   ┌─────────┐      ┌─────────┐
                   │  Postgres│     │  Redis  │
                   │  :5432   │     │  :6379  │
                   └─────────┘      └─────────┘
```

## Step-by-Step Deployment

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install nginx
sudo apt install nginx -y

# Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install pnpm
npm install -g pnpm

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Install Redis
sudo apt install redis-server -y

# Install certbot for SSL
sudo apt install certbot python3-certbot-nginx -y
```

### 2. Database Setup

```bash
# PostgreSQL setup
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE fvspec;
CREATE USER fvspec_user WITH ENCRYPTED PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE fvspec TO fvspec_user;
\q

# Redis setup (should already be running)
sudo systemctl status redis-server
```

### 3. Application Deployment

#### Clone Repository

```bash
# Create application directory
mkdir -p /home/quinn/fvspec-leaderboard
cd /home/quinn/fvspec-leaderboard

# Clone repository
git clone https://github.com/GaloisInc/fvspec.git .
# Or if using deploy key:
# git clone git@github.com:GaloisInc/fvspec.git .

# Navigate to leaderboard
cd leaderboard
```

#### Install Dependencies

```bash
pnpm install
```

#### Configure Environment

```bash
# Create environment file
cat > .env <<EOF
# Database
DATABASE_URL=postgresql://fvspec_user:your-secure-password@localhost:5432/fvspec

# Redis
REDIS_URL=redis://localhost:6379

# API
API_TOKEN=$(openssl rand -hex 32)
PORT=3001
NODE_ENV=production

# Worker
RUNNER_NAME=production-runner-01
RUNNER_TRUST=internal
TIME_LIMIT_SEC=7200
MEMORY_MB=16000
WORKER_CONCURRENCY=1

# Frontend (for build time)
NEXT_PUBLIC_API_URL=https://leaderboard.fvspec.org/api
EOF

# Secure the file
chmod 600 .env
```

#### Build Frontend

```bash
cd packages/web

# For static export, first update next.config.ts:
# (See next section for details)

# Build
pnpm build

# Verify build output
ls -la out/
```

#### Run Database Migrations

```bash
cd ../api
pnpm exec drizzle-kit push
```

### 4. Nginx Configuration

#### Copy Configuration Files

```bash
# Copy nginx config
sudo cp /home/quinn/fvspec-leaderboard/leaderboard/operations/nginx-leaderboard.conf \
  /etc/nginx/sites-available/leaderboard.fvspec.org

# Update the root path in the config if needed
sudo nano /etc/nginx/sites-available/leaderboard.fvspec.org
# Change: root /home/quinn/fvspec-leaderboard/leaderboard/packages/web/out;

# Create symlink
sudo ln -s /etc/nginx/sites-available/leaderboard.fvspec.org \
  /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

#### Setup SSL

```bash
# Get SSL certificate
sudo certbot --nginx -d leaderboard.fvspec.org

# Test auto-renewal
sudo certbot renew --dry-run
```

### 5. Systemd Services

#### API Service

```bash
sudo nano /etc/systemd/system/fvspec-api.service
```

```ini
[Unit]
Description=fvspec Leaderboard API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=quinn
WorkingDirectory=/home/quinn/fvspec-leaderboard/leaderboard/packages/api
EnvironmentFile=/home/quinn/fvspec-leaderboard/leaderboard/.env
ExecStart=/usr/local/bin/pnpm start
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### Worker Service

```bash
sudo nano /etc/systemd/system/fvspec-worker.service
```

```ini
[Unit]
Description=fvspec Leaderboard Worker
After=network.target redis.service

[Service]
Type=simple
User=quinn
WorkingDirectory=/home/quinn/fvspec-leaderboard/leaderboard/packages/worker
EnvironmentFile=/home/quinn/fvspec-leaderboard/leaderboard/.env
ExecStart=/usr/local/bin/pnpm start
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable fvspec-api
sudo systemctl enable fvspec-worker

# Start services
sudo systemctl start fvspec-api
sudo systemctl start fvspec-worker

# Check status
sudo systemctl status fvspec-api
sudo systemctl status fvspec-worker
```

### 6. Verify Deployment

```bash
# Check nginx
sudo systemctl status nginx
curl -I https://leaderboard.fvspec.org

# Check API
curl https://leaderboard.fvspec.org/api/health

# Check logs
sudo journalctl -u fvspec-api -f
sudo journalctl -u fvspec-worker -f
```

## Next.js Static Export Configuration

To enable static export, update `packages/web/next.config.ts`:

```typescript
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'export', // Enable static HTML export
  reactCompiler: true,
  turbopack: {},
  // If using API routes, you may need to adjust basePath
  // basePath: process.env.NODE_ENV === 'production' ? '' : '',
}

export default nextConfig
```

**Note**: Static export has some limitations:

- No API routes in Next.js (we use separate Hono API, so this is fine)
- No server-side rendering (all pages are pre-rendered)
- No dynamic routes without `getStaticPaths`

For the leaderboard, static export works well since we're using client-side rendering with API calls.

## Automated Deployment with GitHub Actions

### Setup Deploy Keys

```bash
# On server, generate SSH key
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/github_deploy
# Press enter for no passphrase

# Copy public key
cat ~/.ssh/github_deploy.pub
# Add this to ~/.ssh/authorized_keys

# Copy private key
cat ~/.ssh/github_deploy
# Add this as LEADERBOARD_SSH_KEY secret in GitHub repo
```

### Add GitHub Secrets

Go to GitHub repo → Settings → Secrets and variables → Actions:

- `LEADERBOARD_SSH_KEY`: Private key from above
- `LEADERBOARD_SERVER_IP`: Your server IP address
- `LEADERBOARD_SERVER_USER`: SSH username (e.g., `quinn`)

### Create Workflow

Create `.github/workflows/deploy-leaderboard.yml`:

```yaml
name: Deploy Leaderboard

on:
  push:
    branches:
      - main
    paths:
      - 'leaderboard/packages/web/**'
      - '.github/workflows/deploy-leaderboard.yml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'pnpm'
          cache-dependency-path: 'leaderboard/pnpm-lock.yaml'

      - name: Install dependencies
        run: |
          cd leaderboard
          pnpm install

      - name: Build frontend
        run: |
          cd leaderboard/packages/web
          pnpm build

      - name: Deploy to server
        env:
          SSH_KEY: ${{ secrets.LEADERBOARD_SSH_KEY }}
          SERVER_IP: ${{ secrets.LEADERBOARD_SERVER_IP }}
          SERVER_USER: ${{ secrets.LEADERBOARD_SERVER_USER }}
        run: |
          mkdir -p ~/.ssh
          echo "$SSH_KEY" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key

          # Deploy static files
          rsync -avz --delete \
            -e "ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=no" \
            leaderboard/packages/web/out/ \
            $SERVER_USER@$SERVER_IP:/home/$SERVER_USER/fvspec-leaderboard/leaderboard/packages/web/out/

          # Clean up
          rm ~/.ssh/deploy_key
```

## Updating the Deployment

### Frontend Only

```bash
cd /home/quinn/fvspec-leaderboard/leaderboard/packages/web
git pull
pnpm install
pnpm build
# Nginx will automatically serve new files
```

### API Update

```bash
cd /home/quinn/fvspec-leaderboard/leaderboard/packages/api
git pull
pnpm install
sudo systemctl restart fvspec-api
```

### Worker Update

```bash
cd /home/quinn/fvspec-leaderboard/leaderboard/packages/worker
git pull
pnpm install
sudo systemctl restart fvspec-worker
```

### Database Migration

```bash
cd /home/quinn/fvspec-leaderboard/leaderboard/packages/api
pnpm exec drizzle-kit push
sudo systemctl restart fvspec-api
```

## Monitoring and Maintenance

### Log Files

```bash
# Nginx logs
sudo tail -f /var/log/nginx/leaderboard.access.log
sudo tail -f /var/log/nginx/leaderboard.error.log

# Application logs
sudo journalctl -u fvspec-api -f
sudo journalctl -u fvspec-worker -f

# PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-*.log

# Redis logs
sudo journalctl -u redis-server -f
```

### Health Checks

```bash
# Check all services
sudo systemctl status nginx
sudo systemctl status fvspec-api
sudo systemctl status fvspec-worker
sudo systemctl status postgresql
sudo systemctl status redis-server

# Check ports
sudo netstat -tlnp | grep -E '(80|443|3001|5432|6379)'

# Test endpoints
curl https://leaderboard.fvspec.org/health
curl https://leaderboard.fvspec.org/api/health
```

### Backup Strategy

```bash
# PostgreSQL backup
pg_dump -U fvspec_user fvspec > fvspec_backup_$(date +%Y%m%d).sql

# Automated daily backup (cron)
0 2 * * * pg_dump -U fvspec_user fvspec | gzip > /backups/fvspec_$(date +\%Y\%m\%d).sql.gz
```

## Troubleshooting

See the main README.md for common issues and solutions.

## Security Considerations

1. **Firewall**: Use UFW to restrict access

   ```bash
   sudo ufw allow 22/tcp  # SSH
   sudo ufw allow 80/tcp  # HTTP
   sudo ufw allow 443/tcp # HTTPS
   sudo ufw enable
   ```

2. **Database**: Ensure PostgreSQL only listens on localhost
3. **Redis**: Bind Redis to localhost only
4. **Secrets**: Never commit `.env` files to git
5. **Updates**: Regularly update system packages
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

## Related Documentation

- **Operations Overview**: `./README.md`
- **Nginx Config**: `./nginx-leaderboard.conf`
- **Architecture**: `../AGENTS.md`
