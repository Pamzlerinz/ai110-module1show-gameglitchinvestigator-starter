def check_guess(guess, secret):
    if guess == secret:
        return "Win"
    if guess > secret:
        return "Too High"
    return "Too Low"


def closeness_hint(guess, secret):
    return ""
