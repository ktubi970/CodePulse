def normalize_record(data: dict) -> dict:
    # Doit être séparé en helpers normalize_email et normalize_tags
    email = data.get('email', '').strip().lower()
    raw_tags = data.get('tags', [])
    tags = sorted(list({t.strip().lower() for t in raw_tags if t.strip()}))
    return {'email': email, 'tags': tags}
