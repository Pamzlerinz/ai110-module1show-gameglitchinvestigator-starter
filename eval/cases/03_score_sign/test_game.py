from game import update_score


def test_too_high_always_deducts_points():
    assert update_score(100, "Too High", 2) == 95
    assert update_score(100, "Too High", 3) == 95


def test_too_low_deducts_points():
    assert update_score(100, "Too Low", 1) == 95


def test_win_bonus():
    assert update_score(0, "Win", 1) == 90


def test_win_bonus_floor():
    assert update_score(0, "Win", 50) == 10
