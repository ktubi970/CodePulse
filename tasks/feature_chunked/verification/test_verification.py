import pytest
from src.chunk import chunked

def test_chunked_invalid():
    with pytest.raises(ValueError):
        list(chunked([1, 2], 0))
