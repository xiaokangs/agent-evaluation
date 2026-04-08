from solution import binary_search


def test_found_in_middle():
    assert binary_search([1, 3, 5, 7, 9], 5) == 2

def test_found_at_start():
    assert binary_search([1, 3, 5, 7, 9], 1) == 0

def test_found_at_end():
    assert binary_search([1, 3, 5, 7, 9], 9) == 4

def test_not_found():
    assert binary_search([1, 3, 5, 7, 9], 4) == -1

def test_single_element_found():
    assert binary_search([42], 42) == 0

def test_single_element_not_found():
    assert binary_search([42], 7) == -1

def test_even_length():
    assert binary_search([2, 4, 6, 8], 6) == 2
    assert binary_search([2, 4, 6, 8], 1) == -1

def test_target_larger_than_all():
    # Triggers the off-by-one: right=len(arr) causes arr[mid] IndexError
    # when the search range extends past the last valid index
    assert binary_search([2, 4, 6, 8], 9) == -1
    assert binary_search([1, 3, 5], 10) == -1
