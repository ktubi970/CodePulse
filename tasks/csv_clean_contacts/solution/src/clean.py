import csv
import io


def clean_contacts(csv_text: str) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["name", "email"])
    seen: set[str] = set()
    for row in csv.DictReader(io.StringIO(csv_text)):
        email = (row.get("email") or "").strip().lower()
        if "@" not in email or email in seen:
            continue
        seen.add(email)
        writer.writerow([(row.get("name") or "").strip(), email])
    return out.getvalue()
