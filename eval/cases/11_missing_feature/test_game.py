from game import check_guess, closeness_hint


def test_basic_outcomes_still_work():
    assert check_guess(50, 50) == "Win"


def test_very_close_hint():
    assert closeness_hint(47, 50) == "Very close"


def test_far_away_has_no_hint():
    assert closeness_hint(10, 50) == ""
