#!/usr/bin/env bash
# Memory limiting utilities for benchmark operations
# Provides functions to wrap commands with cgroup or prlimit memory limits

# Parse human-readable size (e.g., "8G", "512M") to bytes
# Usage: parse_size_to_bytes "8G"
parse_size_to_bytes() {
    local size="$1"
    local num="${size%[GMKgmk]}"
    local suffix="${size: -1}"
    case "$suffix" in
        G|g) echo $((num * 1024 * 1024 * 1024)) ;;
        M|m) echo $((num * 1024 * 1024)) ;;
        K|k) echo $((num * 1024)) ;;
        *)   echo "$size" ;;  # Assume already in bytes
    esac
}

# Build command prefix for memory limiting
# Returns a command prefix string or empty if no limit specified
# Usage: MEMORY_CMD=$(build_memory_cmd "25G")           # MemoryHigh only
#        MEMORY_CMD=$(build_memory_cmd "25G" "30G")     # MemoryHigh + MemoryMax
#        $MEMORY_CMD nice -n 19 my_command
#
# Parameters:
#   $1 - memory_high: Soft limit (throttling), e.g. "25G"
#   $2 - memory_max: Optional hard limit (OOM kill), e.g. "30G" (omit for no hard limit)
build_memory_cmd() {
    local memory_high="$1"
    local memory_max="${2:-}"  # Optional

    [[ -z "$memory_high" ]] && return 0

    # Build systemd-run parameters
    local systemd_params="-p MemoryHigh=$memory_high -p MemorySwapMax=0"
    if [[ -n "$memory_max" ]]; then
        systemd_params="$systemd_params -p MemoryMax=$memory_max"
    fi

    # Try systemd-run first (cgroups v2 - most reliable)
    # Test with a simple scope to check availability
    if systemd-run --user --scope true 2>/dev/null; then
        # systemd-run with user scope works
        echo "systemd-run --user --scope $systemd_params --"
    elif systemd-run --scope true 2>/dev/null; then
        # System-level scope works (may need root)
        echo "systemd-run --scope $systemd_params --"
    elif command -v prlimit &>/dev/null; then
        # Fall back to prlimit (virtual memory limit, less precise but portable)
        # Use memory_max if provided, otherwise memory_high
        local limit="${memory_max:-$memory_high}"
        local bytes
        bytes=$(parse_size_to_bytes "$limit")
        echo "prlimit --as=$bytes --"
    else
        echo "WARNING: No memory limiting available (install systemd or util-linux)" >&2
        # Return empty - command will run without memory limit
    fi
}

# Check if exit code indicates OOM kill
# Usage: if is_oom_exit "$exit_code"; then ...
is_oom_exit() {
    local exit_code="$1"
    # 137 = 128 + 9 (SIGKILL, common for OOM)
    # 134 = 128 + 6 (SIGABRT, sometimes used)
    [[ "$exit_code" -eq 137 ]] || [[ "$exit_code" -eq 134 ]]
}
