from game import play_round


def test_low_guess_on_odd_attempt():
    assert play_round(9, 50, 1) == "Too Low"


def test_low_guess_on_even_attempt():
    assert play_round(9, 50, 2) == "Too Low"


def test_win_on_even_attempt():
    assert play_round(50, 50, 4) == "Win"


def test_high_guess_on_even_attempt():
    assert play_round(60, 50, 2) == "Too High"
