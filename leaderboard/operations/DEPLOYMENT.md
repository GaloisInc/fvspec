# Deployment Guide

This guide covers deploying the fvspec leaderboard to a production server using nginx.

## Quick Start Checklist

- [x] EC2 server: `ec2-35-95-72-128.us-west-2.compute.amazonaws.com`
- [x] Existing monorepo at `/home/quinnd/fvspec/`
- [x] Server with nginx installed (Ubuntu/Debian recommended)
- [ ] PostgreSQL and Redis running
- [x] Node.js 20+ installed
- [x] SSL certificate (via certbot, optional for prototype)
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
npm install
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

# Build (creates .next directory with optimized production build)
npm run build

# Verify build output
ls -la .next/
```

**Note:** The current setup uses Next.js with server-side rendering (NOT static export).
The build creates a `.next` directory that requires `next start` to serve.

#### Run Database Migrations

```bash
cd ../api
npx drizzle-kit push
```

### 4. Nginx Configuration

#### Install Nginx Configuration

**NOTE:** The nginx config is NOT symlinked due to certbot needing write access.
Instead, copy the file and manually sync changes after git updates:

```bash
# Copy nginx config from repository to sites-available
sudo ln -sf /home/quinnd/fvspec/leaderboard/operations/nginx-leaderboard.conf \
  /etc/nginx/sites-available/fvspec-web

# Enable the site by symlinking to sites-enabled
sudo ln -sf /etc/nginx/sites-available/fvspec-web \
  /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm -f /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

**After git pull with nginx changes:**

```bash
sudo cp /home/quinnd/fvspec/leaderboard/operations/nginx-leaderboard.conf \
  /etc/nginx/sites-available/fvspec-leaderboard
sudo nginx -t && sudo systemctl reload nginx
```

#### Setup SSL

**IMPORTANT:** The current deployment uses AWS Elastic Load Balancer (ELB) for SSL termination.

**DO NOT run certbot** - it will conflict with the ELB's SSL configuration.

**Current architecture:**

```
Internet → AWS ELB (HTTPS:443) → EC2 nginx (HTTP:80) → Services
          ↑ Handles SSL         ↑ Plain HTTP only
```

The nginx configuration should:

- Listen on port 80 (HTTP) only
- Trust `X-Forwarded-Proto` headers from ELB
- Let ELB handle all SSL/TLS termination

**If you need to manage SSL certificates:**

- Configure them in AWS Certificate Manager (ACM)
- Attach them to the ELB listener
- Never run certbot on the EC2 instance

### 5. Systemd Services

#### Install Service Files via Symlinks

Symlink service files from the repository as the single source of truth:

```bash
# Symlink all three service files
sudo ln -sf /home/quinnd/fvspec/leaderboard/operations/fvspec-web.service \
  /etc/systemd/system/fvspec-web.service

sudo ln -sf /home/quinnd/fvspec/leaderboard/operations/fvspec-api.service \
  /etc/systemd/system/fvspec-api.service

sudo ln -sf /home/quinnd/fvspec/leaderboard/operations/fvspec-worker.service \
  /etc/systemd/system/fvspec-worker.service

# Reload systemd
sudo systemctl daemon-reload
```

**After git pull with service file changes:**

```bash
sudo systemctl daemon-reload
sudo systemctl restart fvspec-web fvspec-api fvspec-worker
```

**Why symlinks?** Service definitions live in the repository (single source of truth).
Updates via `git pull` are automatically reflected after `systemctl daemon-reload && systemctl restart`.

The service files are located in `/home/quinnd/fvspec/leaderboard/operations/`:

- `fvspec-web.service` - Web frontend (Next.js SSR on port 3000)
- `fvspec-api.service` - API service (Hono on port 3002)
- `fvspec-worker.service` - Worker service configuration

#### Enable and Start Services

```bash
# Enable services (start automatically on boot)
sudo systemctl enable fvspec-web
sudo systemctl enable fvspec-api
sudo systemctl enable fvspec-worker

# Start services
sudo systemctl start fvspec-web
sudo systemctl start fvspec-api
sudo systemctl start fvspec-worker

# Check status
sudo systemctl status fvspec-web
sudo systemctl status fvspec-api
sudo systemctl status fvspec-worker
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

## Current Architecture: Next.js with Server-Side Rendering

**The frontend currently uses standard Next.js SSR, NOT static export.**

This means:

- `npm run build` creates `.next/` directory (not `out/`)
- Requires `next start` to serve (via systemd service)
- Supports server-side rendering, API routes, dynamic features
- Runs on port 3000 by default

To switch to static export in the future:

1. Add `output: 'export'` to `next.config.ts`
2. Build will create `out/` directory
3. Can serve directly from nginx (no Node.js process needed)
4. Limitations: no SSR, no API routes, no dynamic routes without `getStaticPaths`

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

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'
          cache-dependency-path: 'leaderboard/package-lock.json'

      - name: Install dependencies
        run: |
          cd leaderboard
          npm ci

      - name: Build frontend
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
npm install
npm run build
# Nginx will automatically serve new files
```

### API Update

```bash
cd /home/quinnd/fvspec/leaderboard/packages/api
git pull
npm install
sudo systemctl restart fvspec-api
```

### Worker Update

```bash
cd /home/quinnd/fvspec/leaderboard/packages/worker
git pull
npm install
sudo systemctl restart fvspec-worker
```

### Database Migration

```bash
cd /home/quinnd/fvspec/leaderboard/packages/api
npx drizzle-kit push
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
