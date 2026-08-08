import pytest
from src.parse import parse_bool

def test_verif_parse_bool_invalid():
    with pytest.raises(ValueError):
        parse_bool('sometimes')
