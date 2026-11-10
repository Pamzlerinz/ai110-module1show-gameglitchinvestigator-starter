---
id: off-by-one-counter
title: Off-by-one in counters and initial values
repair: adjust_int_constant
---
# Off-by-one in counters and initial values

## Symptoms
Attempts left is one less than the limit before the player has guessed. A counter starts at 1 instead of 0, or a range or randint upper bound is one too small or too large. Tests like test_attempts_left_starts_at_limit fail with an expected 8 but got 7.

## Root cause
An integer constant is off by one: an attempts counter initialized to 1, an extra + 1 or - 1 in a bound, or an inclusive limit treated as exclusive.

## Fix recipe
Adjust the single integer constant (or remove the stray + 1 / - 1) so the initial attempts value is 0 and the count of attempts left equals the attempt limit at the start of a game.
