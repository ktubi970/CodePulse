from src.slug import slugify

def test_slugify_complex():
    assert slugify('  --  Python 3.12 Rules!! -- ') == 'python-3-12-rules'
