from src.pricing import calculate_price, discount_rate

def test_discount_rate_extracted():
    assert discount_rate('VIP', 50.0) == 0.20
