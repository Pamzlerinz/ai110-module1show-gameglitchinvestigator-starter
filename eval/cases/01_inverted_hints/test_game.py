from game import check_guess, hint_for


def test_outcome_labels():
    assert check_guess(60, 50) == "Too High"
    assert check_guess(40, 50) == "Too Low"


def test_hint_tells_player_to_go_lower_when_too_high():
    assert "LOWER" in hint_for(60, 50)


def test_hint_tells_player_to_go_higher_when_too_low():
    assert "HIGHER" in hint_for(40, 50)


def test_win_message():
    assert hint_for(50, 50) == "🎉 Correct!"
