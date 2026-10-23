import pytest
from src.config_parser import parse_config


def test_verif_config():
    assert parse_config({'version': 2, 'name': 'my_app'}) == {'version': 2, 'name': 'my_app'}
    with pytest.raises(ValueError):
        parse_config({'version': 2, 'name': 'app', 'unknown_key': 123})
