from solution import remove_duplicates


def test_no_duplicates():
    assert remove_duplicates([1, 2, 3]) == [1, 2, 3]

def test_all_duplicates():
    assert remove_duplicates([1, 1, 1]) == [1]

def test_preserves_order():
    result = remove_duplicates([3, 1, 2, 1, 3])
    assert result == [3, 1, 2], f"Expected [3, 1, 2], got {result}"

def test_preserves_first_occurrence():
    result = remove_duplicates([5, 1, 5, 2, 1])
    assert result == [5, 1, 2], f"Expected [5, 1, 2], got {result}"

def test_strings():
    result = remove_duplicates(["a", "b", "a", "c"])
    assert result == ["a", "b", "c"]

def test_empty():
    assert remove_duplicates([]) == []

def test_single():
    assert remove_duplicates([42]) == [42]
