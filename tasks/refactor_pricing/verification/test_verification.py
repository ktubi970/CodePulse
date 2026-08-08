from src.pricing import calculate_price, discount_rate

def test_verif_pricing():
    assert discount_rate('member', 150.0) == 0.10
    assert calculate_price('member', 150.0) == 135.0
