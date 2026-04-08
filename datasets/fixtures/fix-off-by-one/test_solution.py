from solution import sum_range


def test_basic():
    assert sum_range(1, 5) == 15   # 1+2+3+4+5

def test_single():
    assert sum_range(3, 3) == 3

def test_zero_start():
    assert sum_range(0, 4) == 10  # 0+1+2+3+4
