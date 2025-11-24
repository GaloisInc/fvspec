# fvspec Server Operations Guide

## Server Specs
- Ubuntu EC2: 16 vCPU, 32GB RAM, 200GB storage

## Resolved Issues

### File Descriptor Exhaustion Causing Stalls

**Symptoms:**
- Job stalls/freezes during execution (stdout stops updating)
- Usually gets stuck on `lean-lsp-mcp` tool calls
- Only 1 vCPU at 100% when stalled (vs distributed load when healthy)
- No I/O activity (`iotop -o` shows nothing)
- Process still shows up in `ps aux | rg "fvspec"` but appears hung
- Happens across different `--parallelism` values

**Root Cause:**
Default `ulimit -n` of 1024 file descriptors is insufficient for high parallelism. Each concurrent task uses multiple FDs for:
- Lean LSP server connections
- SQLite database connections
- File I/O for generated Lean files
- MCP tool sockets
- inspect_ai internal pipes/sockets

With moderate parallelism (16-32 concurrent tasks), the 1024 FD limit is easily exhausted, causing deadlock.

**Solution:**
Increase file descriptor limit to 65536:

```bash
# Check current limit
ulimit -n

# Temporary fix (current session)
ulimit -n 65536

# Permanent fix - add to /etc/security/limits.conf
sudo sh -c 'echo "username soft nofile 65536" >> /etc/security/limits.conf'
sudo sh -c 'echo "username hard nofile 65536" >> /etc/security/limits.conf'

# Log out and back in for permanent fix to take effect
```

**Verification:**
```bash
# Monitor FD usage during run
watch -n 5 'lsof -p <pid> | wc -l'

# Check socket statistics
ss -s
```

Healthy runs show:
- FD count stays under 100 per process
- Few established TCP connections (5-10)
- No socket exhaustion

**Code Improvements:**
Additional fixes were made to ensure proper cleanup of database connections:
- `orchestration.py:306-311` - Close DB session after function discovery completes
- `declaration.py:724-731` - Safety net to close any remaining DB sessions in cleanup phase

These changes ensure database connections and file descriptors are released promptly when moving between samples. 
