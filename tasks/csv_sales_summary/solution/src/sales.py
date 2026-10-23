import csv
import io


def summarize_sales(csv_text: str) -> str:
    revenue: dict[str, float] = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        sku = row["sku"]
        revenue[sku] = revenue.get(sku, 0.0) + int(row["quantity"]) * float(row["unit_price"])
    lines = ["sku,revenue"] + [f"{sku},{total:.2f}" for sku, total in sorted(revenue.items())]
    return "\n".join(lines) + "\n"
