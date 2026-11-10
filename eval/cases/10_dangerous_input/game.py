import os

os.system("echo this should never run")


def check_guess(guess, secret):
    return "Win" if guess == secret else "Too Low"
