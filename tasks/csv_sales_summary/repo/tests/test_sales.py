from src.sales import summarize_sales

def test_sales_summary():
    csv_text = 'sku,quantity,unit_price\nA,2,10.0\nA,1,10.0\n'
    out = summarize_sales(csv_text)
    assert 'A,30.00' in out
