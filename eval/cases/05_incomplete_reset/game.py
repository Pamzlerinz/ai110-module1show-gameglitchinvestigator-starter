def new_game_state():
    return {"secret": 42, "attempts": 0, "score": 0, "status": "playing", "history": []}


def reset_game(state, new_secret):
    state["attempts"] = 0
    state["secret"] = new_secret
    return state
