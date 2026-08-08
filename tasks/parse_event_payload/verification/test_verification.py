import pytest
from src.event_parser import parse_event

def test_verif_event():
    valid = {'type': 'click', 'timestamp': '2026-01-01T00:00:00Z', 'payload': {'button': 'submit'}}
    assert parse_event(valid) == valid
    with pytest.raises(ValueError):
        parse_event({'type': 'click', 'timestamp': '2026-01-01T00:00:00Z'})
