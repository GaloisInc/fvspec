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

    # Load done ranges into associative array
    declare -A done_map=()
    while read -r start end range_variant rest; do
        # Skip comments and empty lines
        [[ "$start" =~ ^# ]] && continue
        [[ -z "$start" ]] && continue

        # Only include ranges for this variant
        if [[ "$range_variant" == "$variant" ]]; then
            done_map["$start:$end"]=1
        fi
    done < "$done_file"

    # Filter queue, removing done ranges
    local filtered=()
    local skipped_count=0
    for chunk_spec in "${queue_ref[@]}"; do
        if [[ -z "${done_map[$chunk_spec]:-}" ]]; then
            filtered+=("$chunk_spec")
        else
            echo "  Skipping completed range: $chunk_spec (in done.txt)"
            ((skipped_count++))
            ((completed_ref++))
        fi
    done

    queue_ref=("${filtered[@]}")

    if [[ $skipped_count -gt 0 ]]; then
        echo "Filtered out $skipped_count completed chunks from done.txt"
    fi
}
