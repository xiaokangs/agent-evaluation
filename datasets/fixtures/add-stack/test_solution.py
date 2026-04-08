import pytest
from solution import Stack


def test_is_empty_on_creation():
    s = Stack()
    assert s.is_empty() is True

def test_size_zero_on_creation():
    s = Stack()
    assert s.size() == 0

def test_push_and_size():
    s = Stack()
    s.push(1)
    assert s.size() == 1
    s.push(2)
    assert s.size() == 2

def test_is_empty_after_push():
    s = Stack()
    s.push(42)
    assert s.is_empty() is False

def test_peek():
    s = Stack()
    s.push(10)
    s.push(20)
    assert s.peek() == 20
    assert s.size() == 2  # peek must not remove

def test_pop_lifo_order():
    s = Stack()
    s.push(1)
    s.push(2)
    s.push(3)
    assert s.pop() == 3
    assert s.pop() == 2
    assert s.pop() == 1

def test_pop_reduces_size():
    s = Stack()
    s.push("a")
    s.push("b")
    s.pop()
    assert s.size() == 1

def test_pop_empty_raises():
    s = Stack()
    with pytest.raises(IndexError):
        s.pop()

def test_peek_empty_raises():
    s = Stack()
    with pytest.raises(IndexError):
        s.peek()

def test_is_empty_after_pop_all():
    s = Stack()
    s.push(1)
    s.pop()
    assert s.is_empty() is True
