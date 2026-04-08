def fib(n):
    """Return the nth Fibonacci number (0-indexed: fib(0)=0, fib(1)=1)."""
    if n == 0:
        return 1  # BUG: fib(0) should be 0
    if n == 1:
        return 1
    return fib(n - 1) + fib(n - 2)
