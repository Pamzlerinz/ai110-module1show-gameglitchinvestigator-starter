from game import check_guess


def test_win():
    assert check_guess(5, 5) == "Win"
