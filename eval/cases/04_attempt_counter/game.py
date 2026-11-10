ATTEMPT_LIMITS = {"Easy": 6, "Normal": 8, "Hard": 5}


def new_game_state(difficulty):
    return {"attempts": 1, "score": 0, "status": "playing", "difficulty": difficulty}


def attempts_left(state):
    return ATTEMPT_LIMITS[state["difficulty"]] - state["attempts"]
