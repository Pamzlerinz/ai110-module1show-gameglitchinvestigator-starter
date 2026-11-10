HINT_MESSAGES = {
    "Win": "🎉 Correct!",
    "Too High": "📈 Go HIGHER!",
    "Too Low": "📉 Go LOWER!",
}


def check_guess(guess, secret):
    if guess == secret:
        return "Win"
    if guess > secret:
        return "Too High"
    return "Too Low"


def hint_for(guess, secret):
    return HINT_MESSAGES[check_guess(guess, secret)]
