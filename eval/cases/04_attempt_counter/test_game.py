from game import attempts_left, new_game_state


def test_attempts_left_starts_at_limit():
    assert attempts_left(new_game_state("Normal")) == 8


def test_attempts_left_after_one_guess():
    state = new_game_state("Easy")
    state["attempts"] += 1
    assert attempts_left(state) == 5


def test_new_game_score_is_zero():
    assert new_game_state("Hard")["score"] == 0
