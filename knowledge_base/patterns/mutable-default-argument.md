---
id: mutable-default-argument
title: Mutable default argument leaks state between games
repair: fix_mutable_default
---
# Mutable default argument leaks state between games

## Symptoms
Guess history from a previous game shows up in a new game. A list grows across calls even when a fresh game starts. Tests like test_history_not_shared_between_games fail with a list containing old guesses.

## Root cause
A function uses a mutable default argument such as history=[] or cache={}. Python evaluates the default once, so every call shares the same list object.

## Fix recipe
Use None as the default and create a new list inside the function: def record_guess(guess, history=None): if history is None: history = [].
