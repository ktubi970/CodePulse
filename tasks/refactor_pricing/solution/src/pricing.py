def discount_rate(customer_kind: str, subtotal: float) -> float:
    if customer_kind == 'VIP':
        return 0.20
    if customer_kind == 'member':
        return 0.10 if subtotal >= 100 else 0.05
    return 0.0


def calculate_price(customer_kind: str, subtotal: float) -> float:
    return subtotal * (1.0 - discount_rate(customer_kind, subtotal))
