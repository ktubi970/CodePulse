from src.window import window

def test_window_basic():
    data = [10, 20, 30, 40, 50]
    # Intentionally asserts correct behavior, which fails currently
    assert len(window(data, 1, 3)) == 3
