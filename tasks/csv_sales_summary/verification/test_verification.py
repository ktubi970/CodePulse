from src.sales import summarize_sales

def test_verif_sales():
    csv_text = 'sku,quantity,unit_price\nB,1,5.50\nA,2,10.00\n'
    lines = summarize_sales(csv_text).strip().splitlines()
    assert lines[0] == 'sku,revenue'
    assert lines[1] == 'A,20.00'
    assert lines[2] == 'B,5.50'
