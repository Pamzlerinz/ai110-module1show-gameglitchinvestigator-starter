---
id: inverted-hint
title: Inverted hint direction
repair: swap_direction_words
---
# Inverted hint direction

## Symptoms
The game tells the player to go higher when the guess is too high, or go lower when the guess is too low. Hint text points the wrong direction. A test like test_hint_direction or test_hint_tells_player_to_go_lower fails with an assertion that LOWER or HIGHER is not in the message.

## Root cause
The outcome labels ("Too High", "Too Low") are correct but the user-facing messages attached to them are swapped, usually inside a HINT_MESSAGES dictionary or an if/else that returns message strings. The comparison itself is fine; only the words and arrow emoji are inverted.

## Fix recipe
Swap the direction words in the hint strings: "Too High" must say "Go LOWER" and "Too Low" must say "Go HIGHER". Swap the matching up/down arrow emoji too so the icon agrees with the text. Do not touch the comparison logic.
