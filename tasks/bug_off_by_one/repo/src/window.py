def window(values: list, start: int, width: int) -> list:
    if start < 0 or width < 0:
        return []
    # Buggy slicing: start + width + 1 returns width + 1 elements
    return values[start : start + width + 1]
