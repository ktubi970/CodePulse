def parse_bool(val: str) -> bool:
    s = str(val).strip().lower()
    if s in ('true', '1', 'yes'): return True
    return False
