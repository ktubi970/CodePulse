from src.cache import make_cache_key

def test_cache_collision():
    assert make_cache_key('ab', 'c') != make_cache_key('a', 'bc')
