def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_tags(tags: list) -> list:
    return sorted({t.strip().lower() for t in tags if t.strip()})


def normalize_record(data: dict) -> dict:
    return {
        "email": normalize_email(data.get("email", "")),
        "tags": normalize_tags(data.get("tags", [])),
    }
