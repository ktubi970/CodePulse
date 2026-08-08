from src.normalize import normalize_record

def test_verif_normalize():
    res = normalize_record({'email': '  A@B.COM  ', 'tags': ['x', 'X', 'y']})
    assert res == {'email': 'a@b.com', 'tags': ['x', 'y']}
