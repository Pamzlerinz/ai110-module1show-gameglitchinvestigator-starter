def get_range_for_difficulty(difficulty):
    return {"Easy": (1, 20), "Normal": (1, 100), "Hard": (1, 50)}.get(difficulty, (1, 100))


def is_valid_guess(guess, difficulty):
    low, high = get_range_for_difficulty(difficulty)
    return low < guess < high
