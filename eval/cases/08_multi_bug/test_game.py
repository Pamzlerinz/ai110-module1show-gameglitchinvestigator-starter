from game import submit_guess


def fresh(secret=50):
    return {"secret": secret, "attempts": 0, "score": 0}


def test_hint_direction():
    _, msg = submit_guess(fresh(), 60)
    assert "LOWER" in msg


def test_even_attempt_low_guess():
    state = fresh()
    submit_guess(state, 30)
    outcome, _ = submit_guess(state, 9)
    assert outcome == "Too Low"


def test_wrong_guess_lowers_score():
    state = fresh()
    submit_guess(state, 20)
    submit_guess(state, 70)
    assert state["score"] == -10
