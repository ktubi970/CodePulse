REQUIRED_KEYS = {"type", "timestamp", "payload"}


def parse_event(data: dict) -> dict:
    if set(data) != REQUIRED_KEYS:
        raise ValueError(f"event must have exactly the keys {sorted(REQUIRED_KEYS)}")
    if data["type"] not in ("click", "view"):
        raise ValueError(f"unsupported event type: {data['type']!r}")
    return data
