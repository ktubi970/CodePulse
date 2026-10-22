from src.math_utils import safe_divide


def test_safe_divide_zero():
    assert safe_divide(10, 0) is None
    assert safe_divide(-3.5, 0) is None
