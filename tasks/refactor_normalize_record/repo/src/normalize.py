def normalize_record(data: dict) -> dict:
    # Should be split into normalize_email and normalize_tags helpers
    email = data.get('email', '').strip().lower()
    raw_tags = data.get('tags', [])
    tags = sorted(list({t.strip().lower() for t in raw_tags if t.strip()}))
    return {'email': email, 'tags': tags}
