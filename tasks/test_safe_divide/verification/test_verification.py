from src.math_utils import safe_divide

def test_verif_safe_divide():
    assert safe_divide(10, 0) is None
