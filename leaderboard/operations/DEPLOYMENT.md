# Deployment Guide

This guide covers deploying the fvspec leaderboard to a production server using nginx.

## Quick Start Checklist

- [ ] EC2 server: `ec2-35-95-72-128.us-west-2.compute.amazonaws.com`
- [ ] Existing monorepo at `/home/quinnd/fvspec/`
- [ ] Server with nginx installed (Ubuntu/Debian recommended)
- [ ] PostgreSQL and Redis running
- [ ] Node.js 20+ and pnpm installed
- [ ] SSL certificate (via certbot, optional for prototype)
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

#### Navigate to Existing Repository

The monorepo is already cloned at `/home/quinnd/fvspec/`:

```bash
# Navigate to the leaderboard directory
cd /home/quinnd/fvspec/leaderboard

# Pull latest changes
git pull

# If starting fresh, you might need to clone:
# cd /home/quinnd
# git clone https://github.com/GaloisInc/fvspec.git
```

#### Install Dependencies

```bash
pnpm install
```

#### Configure Environment

```bash
# Navigate to leaderboard directory
cd /home/quinnd/fvspec/leaderboard

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
RUNNER_NAME=prototype-runner-01
RUNNER_TRUST=internal
TIME_LIMIT_SEC=7200
MEMORY_MB=16000
WORKER_CONCURRENCY=1

# Frontend (for build time)
# For prototype without SSL:
NEXT_PUBLIC_API_URL=http://ec2-35-95-72-128.us-west-2.compute.amazonaws.com/api
# For production with SSL:
# NEXT_PUBLIC_API_URL=https://leaderboard.fvspec.org/api
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

#### Install Nginx Configuration via Symlink

Following the operations directory pattern, we symlink the nginx config from the
repository as the single source of truth:

```bash
# Symlink nginx config from repository to sites-available
sudo ln -sf /home/quinnd/fvspec/leaderboard/operations/nginx-leaderboard.conf \
  /etc/nginx/sites-available/fvspec-leaderboard

# Enable the site by symlinking to sites-enabled
sudo ln -sf /etc/nginx/sites-available/fvspec-leaderboard \
  /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm -f /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

**Why symlinks?** Configuration lives in the repository (single source of truth).
Updates via `git pull` are automatically reflected after `nginx -t && nginx -s reload`.

#### Setup SSL (Optional for Prototype)

For the prototype, you can skip SSL and use HTTP only. For production:

```bash
# Option 1: Use custom domain pointed at EC2 IP
sudo certbot --nginx -d leaderboard.fvspec.org

# Option 2: Try with EC2 hostname (may not work with Let's Encrypt)
# sudo certbot --nginx -d ec2-35-95-72-128.us-west-2.compute.amazonaws.com

# Test auto-renewal
sudo certbot renew --dry-run
```

**Note**: Let's Encrypt typically doesn't issue certificates for EC2 hostnames. For the prototype, either:

- Use HTTP without SSL (current nginx config default)
- Point a custom domain at the EC2 IP and use certbot with that domain
- Use a self-signed certificate for testing

### 5. Systemd Services

Following the operations directory pattern, we symlink systemd service files from
the repository as the single source of truth.

#### Install Service Files via Symlinks

```bash
# Symlink API service
sudo ln -sf /home/quinnd/fvspec/leaderboard/operations/fvspec-api.service \
  /etc/systemd/system/fvspec-api.service

# Symlink Worker service
sudo ln -sf /home/quinnd/fvspec/leaderboard/operations/fvspec-worker.service \
  /etc/systemd/system/fvspec-worker.service
```

**Why symlinks?** Service definitions live in the repository (single source of truth).
Updates via `git pull` are automatically available after `systemctl daemon-reload`.

The service files are located in `/home/quinnd/fvspec/leaderboard/operations/`:

- `fvspec-api.service` - API service configuration
- `fvspec-worker.service` - Worker service configuration

#### Enable and Start Services

```bash
# Reload systemd to pick up new service files
sudo systemctl daemon-reload

# Enable services (start automatically on boot)
sudo systemctl enable fvspec-api
sudo systemctl enable fvspec-worker

# Start services
sudo systemctl start fvspec-api
sudo systemctl start fvspec-worker

# Check status
sudo systemctl status fvspec-api
sudo systemctl status fvspec-worker
```

**Note**: After updating service files via `git pull`, run:

```bash
sudo systemctl daemon-reload
sudo systemctl restart fvspec-api  # or fvspec-worker
```

### 6. Verify Deployment

```bash
# Check nginx
sudo systemctl status nginx
curl -I http://ec2-35-95-72-128.us-west-2.compute.amazonaws.com

# Check API
curl http://ec2-35-95-72-128.us-west-2.compute.amazonaws.com/api/health

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
cd /home/quinnd/fvspec/leaderboard/packages/web
git pull
pnpm install
pnpm build
# Nginx will automatically serve new files
```

### API Update

```bash
cd /home/quinnd/fvspec/leaderboard/packages/api
git pull
pnpm install
sudo systemctl restart fvspec-api
```

### Worker Update

```bash
cd /home/quinnd/fvspec/leaderboard/packages/worker
git pull
pnpm install
sudo systemctl restart fvspec-worker
```

### Database Migration

```bash
cd /home/quinnd/fvspec/leaderboard/packages/api
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
