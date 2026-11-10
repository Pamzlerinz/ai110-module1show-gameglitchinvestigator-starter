"""Core game logic for the Number Guessing Game.

Kept free of any Streamlit/UI code so it can be unit tested in isolation.
"""

# FIX: these were backwards - a "Too High" guess needs to go LOWER, and a
# "Too Low" guess needs to go HIGHER, not the other way around. Verified by
# playing the game and checking the printed hint against the outcome label.
HINT_MESSAGES = {
    "Win": "🎉 Correct!",
    "Too High": "📉 Go LOWER!",
    "Too Low": "📈 Go HIGHER!",
}


def get_range_for_difficulty(difficulty: str):
    """Return (low, high) inclusive range for a given difficulty."""
    if difficulty == "Easy":
        return 1, 20
    if difficulty == "Normal":
        return 1, 100
    if difficulty == "Hard":
        return 1, 50
    return 1, 100


def parse_guess(raw: str):
    """
    Parse user input into an int guess.

    Returns: (ok: bool, guess_int: int | None, error_message: str | None)
    """
    if raw is None or raw == "":
        return False, None, "Enter a guess."

    try:
        if "." in raw:
            value = int(float(raw))
        else:
            value = int(raw)
    except (ValueError, TypeError):
        return False, None, "That is not a number."

    return True, value, None


def check_guess(guess: int, secret: int):
    """
    Compare guess to secret and return the outcome string.

    # FIX: app.py used to alternate `secret` between int and str every
    # other attempt, which pushed this comparison into a broken
    # string-vs-int fallback (e.g. "9" > "50" is True lexicographically).
    # Callers now always pass plain ints, so this is a normal numeric
    # comparison. Fixed with Claude in agent mode; verified with
    # tests/test_game_logic.py and a manual playthrough.

    outcome is one of: "Win", "Too High", "Too Low"
    """
    if guess == secret:
        return "Win"
    if guess > secret:
        return "Too High"
    return "Too Low"


def get_hint_message(outcome: str):
    """Look up the user-facing hint message for a given outcome."""
    return HINT_MESSAGES.get(outcome, "")


def update_score(current_score: int, outcome: str, attempt_number: int):
    """Update score based on outcome and attempt number."""
    if outcome == "Win":
        points = 100 - 10 * attempt_number
        if points < 10:
            points = 10
        return current_score + points

    # FIX: "Too High" used to add points on even attempt numbers instead of
    # always deducting for a wrong guess. Both wrong outcomes now behave the
    # same way. Verified with tests/test_game_logic.py.
    if outcome in ("Too High", "Too Low"):
        return current_score - 5

    return current_score
