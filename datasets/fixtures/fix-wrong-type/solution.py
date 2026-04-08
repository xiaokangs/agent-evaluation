def celsius_to_fahrenheit(c):
    """Convert Celsius to Fahrenheit and return a float."""
    return str(c * 9 / 5 + 32)  # BUG: should return float, not str
