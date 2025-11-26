# EC2 Security Group Fix for GitHub Actions Deployment

## Problem

The deployment is failing with:
```
Connection timed out
ssh: connect to host ec2-35-95-72-128.us-west-2.compute.amazonaws.com port 22: Connection timed out
```

This means GitHub Actions cannot reach your EC2 instance on port 22 (SSH).

## Solution

You need to update your EC2 security group to allow SSH access from GitHub Actions.

### Option 1: Allow GitHub Actions IP Ranges (Recommended for Production)

1. **Get GitHub Actions IP ranges:**
   ```bash
   curl https://api.github.com/meta | jq -r '.actions[]'
   ```

2. **Update EC2 Security Group:**
   - Go to AWS Console → EC2 → Security Groups
   - Find the security group attached to your EC2 instance
   - Click "Edit inbound rules"
   - Add a new rule for **each** GitHub Actions CIDR range:
     - Type: SSH
     - Protocol: TCP
     - Port: 22
     - Source: [GitHub Actions CIDR, e.g., 4.175.114.51/32]
   - Save rules

   **Note:** GitHub's IP ranges change occasionally, so you'll need to monitor and update them.

### Option 2: Allow All SSH (Quick Fix, Less Secure)

1. **Update EC2 Security Group:**
   - Go to AWS Console → EC2 → Security Groups
   - Find the security group attached to your EC2 instance
   - Click "Edit inbound rules"
   - Add rule:
     - Type: SSH
     - Protocol: TCP
     - Port: 22
     - Source: 0.0.0.0/0 (anywhere)
   - Save rules

   **⚠️ Security Warning:** This allows SSH from any IP address. Only use for testing or if you have other security measures in place (fail2ban, key-only auth, etc.).

### Option 3: Use GitHub Self-Hosted Runner

Instead of deploying from GitHub Actions, run a self-hosted runner on your EC2 instance or in your VPC:

1. Go to your GitHub repo → Settings → Actions → Runners → New self-hosted runner
2. Follow instructions to install the runner on your EC2 instance or nearby
3. Update `.github/workflows/deploy.yml` to use `runs-on: self-hosted`

This avoids the networking issue entirely since the runner is in your network.

## Testing the Fix

After updating the security group, push a commit to trigger the workflow:

```bash
git commit --allow-empty -m "test: trigger deployment after security group fix"
git push origin main
```

Then monitor the workflow:
```bash
gh run list --workflow=deploy.yml --limit 1
gh run view <run-id> --log
```

You should see "SSH connection successful" instead of "Connection timed out".
