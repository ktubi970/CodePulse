def make_cache_key(ns: str, key: str) -> str:
    # repr() of the tuple keeps both parts distinct: ('ab', 'c') != ('a', 'bc')
    return repr((ns, key))
