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


def play_round(guess, secret, attempt_number):
    if attempt_number % 2 == 0:
        secret = str(secret)
    return check_guess(guess, secret)
