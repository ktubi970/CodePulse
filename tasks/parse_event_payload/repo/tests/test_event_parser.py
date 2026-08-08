import pytest
from src.event_parser import parse_event

def test_event_valid_types():
    with pytest.raises(ValueError):
        parse_event({'type': 'invalid', 'timestamp': '2026-01-01T00:00:00Z', 'payload': {}})
