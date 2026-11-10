from game import (
    check_guess,
    update_score,
    parse_guess,
    get_range_for_difficulty,
    get_hint_message,
)


def test_winning_guess():
    # If the secret is 50 and guess is 50, it should be a win
    result = check_guess(50, 50)
    assert result == "Win"

def test_guess_too_high():
    # If secret is 50 and guess is 60, hint should be "Too High"
    result = check_guess(60, 50)
    assert result == "Too High"

def test_guess_too_low():
    # If secret is 50 and guess is 40, hint should be "Too Low"
    result = check_guess(40, 50)
    assert result == "Too Low"


# --- Regression tests for the bugs fixed in Phase 2 ---

def test_hint_direction_is_not_backwards():
    # FIX regression: "Too High" used to display "Go HIGHER!" and "Too Low"
    # used to display "Go LOWER!" - exactly inverted from what the player
    # needs to do next.
    assert get_hint_message("Too High") == "📉 Go LOWER!"
    assert get_hint_message("Too Low") == "📈 Go HIGHER!"


def test_too_high_always_deducts_points():
    # FIX regression: "Too High" used to award +5 points on even attempt
    # numbers instead of always deducting for a wrong guess.
    assert update_score(current_score=100, outcome="Too High", attempt_number=2) == 95
    assert update_score(current_score=100, outcome="Too High", attempt_number=3) == 95

def test_too_low_deducts_points():
    assert update_score(current_score=100, outcome="Too Low", attempt_number=1) == 95

def test_win_score_uses_attempt_number_without_off_by_one():
    # First successful guess (attempt_number=1) should award 90 points,
    # not 80 (the old formula subtracted an extra 10 due to a +1 bug).
    assert update_score(current_score=0, outcome="Win", attempt_number=1) == 90

def test_win_score_has_floor_of_ten():
    assert update_score(current_score=0, outcome="Win", attempt_number=50) == 10


# --- Edge-case tests for parse_guess (Challenge 1) ---

def test_parse_guess_rejects_empty_input():
    # Edge case: empty string is a common "user submitted nothing" input.
    ok, value, err = parse_guess("")
    assert ok is False
    assert value is None
    assert err is not None

def test_parse_guess_rejects_non_numeric_string():
    # Edge case: non-numeric text should fail gracefully, not crash.
    ok, value, err = parse_guess("banana")
    assert ok is False
    assert value is None
    assert err == "That is not a number."

def test_parse_guess_accepts_negative_numbers():
    # Edge case: negative numbers are valid integers and should parse.
    ok, value, err = parse_guess("-5")
    assert ok is True
    assert value == -5
    assert err is None

def test_parse_guess_accepts_decimal_strings():
    # Edge case: decimal input should be truncated to an int, not crash.
    ok, value, err = parse_guess("42.9")
    assert ok is True
    assert value == 42
    assert err is None

def test_parse_guess_accepts_very_large_numbers():
    # Edge case: extremely large values should still parse without
    # overflow errors (Python ints are arbitrary precision).
    ok, value, err = parse_guess("99999999999999999999")
    assert ok is True
    assert value == 99999999999999999999
    assert err is None


def test_range_for_easy_difficulty():
    assert get_range_for_difficulty("Easy") == (1, 20)
