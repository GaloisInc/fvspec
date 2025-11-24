#!/bin/bash
# Diagnostic script for fvspec leaderboard deployment
# Run this on the EC2 instance to check service status

set -e

echo "================================"
echo "fvspec Leaderboard Diagnostics"
echo "================================"
echo

echo "1. Checking systemd services..."
echo "--------------------------------"
systemctl status fvspec-web fvspec-api fvspec-worker --no-pager || true
echo

echo "2. Checking if services are enabled..."
echo "---------------------------------------"
systemctl is-enabled fvspec-web || echo "fvspec-web: NOT enabled"
systemctl is-enabled fvspec-api || echo "fvspec-api: NOT enabled"
systemctl is-enabled fvspec-worker || echo "fvspec-worker: NOT enabled"
echo

echo "3. Checking listening ports..."
echo "------------------------------"
echo "Expected: 3000 (web), 3002 (api)"
sudo netstat -tlnp | grep -E ':(3000|3002|80)' || echo "No services listening on 3000 or 3002!"
echo

echo "4. Checking nginx status..."
echo "---------------------------"
systemctl status nginx --no-pager || true
echo

echo "5. Checking nginx config..."
echo "---------------------------"
sudo nginx -t
echo

echo "6. Checking service file symlinks..."
echo "-------------------------------------"
ls -la /etc/systemd/system/fvspec-*.service || echo "No service files found!"
echo

echo "7. Checking recent logs (last 20 lines)..."
echo "-------------------------------------------"
echo "=== fvspec-web ==="
sudo journalctl -u fvspec-web -n 20 --no-pager || echo "No logs for fvspec-web"
echo
echo "=== fvspec-api ==="
sudo journalctl -u fvspec-api -n 20 --no-pager || echo "No logs for fvspec-api"
echo
echo "=== fvspec-worker ==="
sudo journalctl -u fvspec-worker -n 20 --no-pager || echo "No logs for fvspec-worker"
echo

echo "8. Checking .env file..."
echo "------------------------"
if [ -f /home/quinnd/fvspec/leaderboard/.env ]; then
    echo ".env file exists"
    echo "PORT from .env: $(grep '^PORT=' /home/quinnd/fvspec/leaderboard/.env || echo 'not set')"
    echo "DATABASE_URL set: $(grep -q '^DATABASE_URL=' /home/quinnd/fvspec/leaderboard/.env && echo 'yes' || echo 'no')"
    echo "REDIS_URL set: $(grep -q '^REDIS_URL=' /home/quinnd/fvspec/leaderboard/.env && echo 'yes' || echo 'no')"
else
    echo ".env file NOT FOUND!"
fi
echo

echo "9. Checking if builds exist..."
echo "------------------------------"
[ -d /home/quinnd/fvspec/leaderboard/packages/web/.next ] && echo "✓ Web build exists (.next)" || echo "✗ Web build missing!"
[ -d /home/quinnd/fvspec/leaderboard/packages/api/dist ] && echo "✓ API build exists (dist)" || echo "✗ API build missing (may not be needed for TS)"
echo

echo "10. Checking PostgreSQL..."
echo "--------------------------"
systemctl status postgresql --no-pager || echo "PostgreSQL not running!"
echo

echo "11. Checking Redis..."
echo "--------------------"
systemctl status redis --no-pager || systemctl status redis-server --no-pager || echo "Redis not running!"
echo

echo "================================"
echo "Diagnostics Complete"
echo "================================"
