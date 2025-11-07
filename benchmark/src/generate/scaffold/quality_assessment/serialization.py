"""Data serialization and conversion utilities for quality assessment."""


def flatten_dict(
    d: dict, parent_key: str = "", sep: str = "_"
) -> dict[str, int | float | str | None]:
    """Recursively flatten a nested dictionary.

    Args:
        d: Dictionary to flatten
        parent_key: Prefix for nested keys
        sep: Separator to join nested keys (default: "_")

    Returns:
        Flattened dictionary with keys joined by separator.
        Booleans are converted to int (0/1) for wandb compatibility.

    Example:
        >>> flatten_dict({"a": 1, "b": {"c": 2, "d": True}})
        {"a": 1, "b_c": 2, "b_d": 1}
    """
    items: list[tuple[str, int | float | str | None]] = []

    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            # Recursively flatten nested dicts
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Handle lists - wandb doesn't handle them well
            if not v:
                # Empty list -> None
                items.append((new_key, None))
            elif all(isinstance(item, str) for item in v):
                # Join string lists (e.g., errors)
                items.append((new_key, ", ".join(v)))
            else:
                # For other lists, just log the length
                items.append((f"{new_key}_count", len(v)))
        elif isinstance(v, bool):
            # Convert bool to int for wandb compatibility
            items.append((new_key, 1 if v else 0))
        else:
            # Primitive values: int, float, str, None
            items.append((new_key, v))

    return dict(items)
