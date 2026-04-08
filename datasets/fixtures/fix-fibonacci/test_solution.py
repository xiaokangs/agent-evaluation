from solution import fib


def test_base_cases():
    assert fib(0) == 0, f"fib(0) should be 0, got {fib(0)}"
    assert fib(1) == 1, f"fib(1) should be 1, got {fib(1)}"

def test_small_values():
    assert fib(2) == 1
    assert fib(3) == 2
    assert fib(4) == 3
    assert fib(5) == 5

def test_larger_values():
    assert fib(10) == 55
    assert fib(12) == 144
