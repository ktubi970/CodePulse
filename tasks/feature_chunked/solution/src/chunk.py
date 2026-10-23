def chunked(values, size: int):
    if size <= 0:
        raise ValueError("size must be positive")
    chunk = []
    for value in values:
        chunk.append(value)
        if len(chunk) == size:
            yield tuple(chunk)
            chunk = []
    if chunk:
        yield tuple(chunk)
