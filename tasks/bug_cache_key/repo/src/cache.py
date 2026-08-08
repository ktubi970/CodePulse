def make_cache_key(ns: str, key: str) -> str:
    # Buggy string concatenation causes collision ('ab', 'c') == ('a', 'bc') == 'abc'
    return ns + key
