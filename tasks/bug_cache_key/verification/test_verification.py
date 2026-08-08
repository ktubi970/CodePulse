from src.cache import make_cache_key

def test_verif_cache_key():
    assert make_cache_key('alpha', 'beta') != make_cache_key('alphab', 'eta')
