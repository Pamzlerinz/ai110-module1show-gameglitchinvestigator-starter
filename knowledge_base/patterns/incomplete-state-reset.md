---
id: incomplete-state-reset
title: Incomplete state reset on New Game
repair: complete_state_reset
---
# Incomplete state reset on New Game

## Symptoms
Clicking New Game after winning or losing keeps showing "You already won" or "Game over". The game is permanently stuck after one round. Score or guess history carries over into the next game. Tests like test_reset_clears_status or test_new_game_resets_score fail.

## Root cause
The reset or new_game handler resets only some keys of the game state (for example attempts and secret) and forgets others such as status, score, and history. Because the stale status is still "won" or "lost", the next run immediately stops.

## Fix recipe
Make the reset function assign every key that the initial state defines: status back to "playing", score back to 0, history back to an empty list, attempts back to 0. Use the initial-state function as the source of truth for default values.
