from solution import word_count


def test_basic():
    assert word_count("hello world") == {"hello": 1, "world": 1}

def test_repeated_word():
    result = word_count("hello world hello")
    assert result == {"hello": 2, "world": 1}

def test_case_insensitive():
    result = word_count("Hello hello HELLO")
    assert result == {"hello": 3}

def test_punctuation_stripped():
    result = word_count("hello, world!")
    assert "hello" in result
    assert "world" in result
    assert result["hello"] == 1
    assert result["world"] == 1

def test_empty_string():
    assert word_count("") == {}

def test_single_word():
    assert word_count("python") == {"python": 1}
