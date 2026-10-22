def parse_bool(val: str) -> bool:
    s = str(val).strip().lower()
    if s in ('true', '1', 'yes'): return True
    if s in ('false', '0', 'no'): return False
    raise TypeError(f'Invalid boolean: {val}')
