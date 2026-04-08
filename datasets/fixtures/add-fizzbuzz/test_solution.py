from solution import fizzbuzz


def test_length():
    assert len(fizzbuzz(15)) == 15

def test_plain_numbers():
    result = fizzbuzz(15)
    assert result[0] == "1"
    assert result[1] == "2"
    assert result[3] == "4"

def test_fizz():
    result = fizzbuzz(15)
    assert result[2] == "Fizz"    # 3
    assert result[5] == "Fizz"    # 6
    assert result[8] == "Fizz"    # 9

def test_buzz():
    result = fizzbuzz(15)
    assert result[4] == "Buzz"    # 5
    assert result[9] == "Buzz"    # 10

def test_fizzbuzz():
    result = fizzbuzz(15)
    assert result[14] == "FizzBuzz"   # 15

def test_first_fizzbuzz_is_15():
    result = fizzbuzz(20)
    assert result[14] == "FizzBuzz"
    assert result[29] if len(result) > 29 else True  # guard

def test_small():
    assert fizzbuzz(1) == ["1"]
    assert fizzbuzz(3) == ["1", "2", "Fizz"]
