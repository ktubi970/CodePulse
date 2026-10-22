def window(values: list, start: int, width: int) -> list:
    if start < 0 or width < 0:
        return []
    return values[start : start + width]
