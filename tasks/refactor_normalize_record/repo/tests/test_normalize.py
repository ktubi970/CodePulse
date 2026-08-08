from src.normalize import normalize_email, normalize_tags

def test_helpers_exist():
    assert normalize_email(' Test@EX.com ') == 'test@ex.com'
    assert normalize_tags([' B ', 'a', 'b']) == ['a', 'b']
