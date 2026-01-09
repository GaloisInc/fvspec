#!/usr/bin/env bash
# Shared library for done.txt filtering

load_and_filter_done_ranges() {
    local done_file="${1:-}"
    local variant="${2:-}"
    local -n queue_ref=$3
    local -n completed_ref=$4

    # If no done file or doesn't exist, skip filtering
    if [[ -z "$done_file" ]] || [[ ! -f "$done_file" ]]; then
        return 0
    fi

    # Load done ranges into arrays
    declare -a done_starts=()
    declare -a done_ends=()
    while read -r start end range_variant rest; do
        # Skip comments and empty lines
        [[ "$start" =~ ^# ]] && continue
        [[ -z "$start" ]] && continue

        # Only include ranges for this variant
        if [[ "$range_variant" == "$variant" ]]; then
            done_starts+=("$start")
            done_ends+=("$end")
        fi
    done < "$done_file"

    # Filter queue, removing chunks that are fully covered by done ranges
    local filtered=()
    local skipped_count=0
    for chunk_spec in "${queue_ref[@]}"; do
        local chunk_start="${chunk_spec%:*}"
        local chunk_end="${chunk_spec#*:}"
        local is_covered=false

        # Check if this chunk is fully covered by any done range
        for i in "${!done_starts[@]}"; do
            local done_start="${done_starts[$i]}"
            local done_end="${done_ends[$i]}"

            # Chunk is covered if: done_start <= chunk_start AND chunk_end <= done_end
            if [[ $done_start -le $chunk_start ]] && [[ $chunk_end -le $done_end ]]; then
                is_covered=true
                echo "  Skipping completed range: $chunk_spec (covered by [$done_start, $done_end) in done.txt)"
                break
            fi
        done

        if [[ "$is_covered" == "false" ]]; then
            filtered+=("$chunk_spec")
        else
            ((skipped_count++))
            ((completed_ref++))
        fi
    done

    queue_ref=("${filtered[@]}")

    if [[ $skipped_count -gt 0 ]]; then
        echo "Filtered out $skipped_count completed chunks from done.txt"
    fi
}
