ALLOWED_KEYS = {"version", "name"}


def parse_config(data: dict) -> dict:
    unknown = set(data) - ALLOWED_KEYS
    if unknown:
        raise ValueError(f"unknown keys: {sorted(unknown)}")
    version = data.get("version")
    if type(version) is not int or version != 2:
        raise ValueError("version must be the integer 2")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    return data
