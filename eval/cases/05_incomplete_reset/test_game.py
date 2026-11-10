from game import new_game_state, reset_game


def finished_game():
    state = new_game_state()
    state.update(attempts=3, score=70, status="won", history=[10, 60, 42])
    return state


def test_reset_clears_status():
    assert reset_game(finished_game(), 7)["status"] == "playing"


def test_reset_clears_score_and_history():
    state = reset_game(finished_game(), 7)
    assert state["score"] == 0
    assert state["history"] == []


def test_reset_sets_new_secret_and_attempts():
    state = reset_game(finished_game(), 7)
    assert state["secret"] == 7
    assert state["attempts"] == 0
