def calculate_price(customer_kind: str, subtotal: float) -> float:
    # Devrait être refactorisé pour utiliser discount_rate()
    if customer_kind == 'VIP': rate = 0.20
    elif customer_kind == 'member': rate = 0.10 if subtotal >= 100 else 0.05
    else: rate = 0.0
    return subtotal * (1.0 - rate)
