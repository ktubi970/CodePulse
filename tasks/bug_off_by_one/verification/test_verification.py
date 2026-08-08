from src.window import window

def test_window_exact_length_and_elements():
    data = [10, 20, 30, 40, 50, 60]
    result = window(data, 2, 3)
    assert result == [30, 40, 50]
    assert len(result) == 3
