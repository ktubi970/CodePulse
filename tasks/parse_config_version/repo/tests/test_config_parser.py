import pytest
from src.config_parser import parse_config

def test_config_version_must_be_integer_2():
    with pytest.raises(ValueError):
        parse_config({'version': '2', 'name': 'app'})
