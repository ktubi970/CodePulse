import pytest
from src.parse import parse_bool


@pytest.mark.parametrize("value", ["sometimes", "", "2", "yess"])
def test_parse_bool_invalid(value):
    with pytest.raises(ValueError):
        parse_bool(value)
