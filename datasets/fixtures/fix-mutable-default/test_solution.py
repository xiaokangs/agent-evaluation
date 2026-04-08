from solution import append_to


def test_independent_calls_do_not_share_state():
    r1 = append_to(1)
    r2 = append_to(2)
    assert r1 == [1], f"Expected [1], got {r1}"
    assert r2 == [2], f"Expected [2], got {r2}"

def test_explicit_list_is_used():
    result = append_to(3, [10, 20])
    assert result == [10, 20, 3]

def test_three_independent_calls():
    a = append_to("x")
    b = append_to("y")
    c = append_to("z")
    assert a == ["x"]
    assert b == ["y"]
    assert c == ["z"]
