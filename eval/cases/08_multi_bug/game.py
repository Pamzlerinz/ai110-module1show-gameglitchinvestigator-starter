HINT_MESSAGES = {"Win": "🎉 Correct!", "Too High": "📈 Go HIGHER!", "Too Low": "📉 Go LOWER!"}


def check_guess(guess, secret):
    try:
        if guess == secret:
            return "Win"
        if guess > secret:
            return "Too High"
        return "Too Low"
    except TypeError:
        g = str(guess)
        if g == secret:
            return "Win"
        if g > secret:
            return "Too High"
        return "Too Low"


def submit_guess(state, guess):
    state["attempts"] += 1
    secret = state["secret"]
    if state["attempts"] % 2 == 0:
        secret = str(secret)
    outcome = check_guess(guess, secret)
    if outcome == "Too High" and state["attempts"] % 2 == 0:
        state["score"] = state["score"] + 5
    elif outcome != "Win":
        state["score"] = state["score"] - 5
    return outcome, HINT_MESSAGES[outcome]
