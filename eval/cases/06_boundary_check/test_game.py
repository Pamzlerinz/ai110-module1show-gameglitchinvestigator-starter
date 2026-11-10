from game import is_valid_guess


def test_low_boundary_is_valid():
    assert is_valid_guess(1, "Easy")


def test_high_boundary_is_valid():
    assert is_valid_guess(20, "Easy")


def test_middle_is_valid():
    assert is_valid_guess(10, "Easy")


def test_outside_range_is_invalid():
    assert not is_valid_guess(0, "Easy")
    assert not is_valid_guess(21, "Easy")
