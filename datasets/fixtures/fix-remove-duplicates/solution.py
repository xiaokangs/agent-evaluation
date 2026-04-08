def remove_duplicates(items):
    """Remove duplicate values from a list while preserving original order."""
    return list(set(items))  # BUG: set() does not preserve insertion order
