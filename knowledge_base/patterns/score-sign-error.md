---
id: score-sign-error
title: Score sign error on wrong guesses
repair: flip_arith_sign
---
# Score sign error on wrong guesses

## Symptoms
The score goes up after a wrong guess, or the score increases on even attempts and decreases on odd attempts. Tests like test_too_high_always_deducts_points or test_wrong_guess_lowers_score fail with an expected value of 95 but got 105.

## Root cause
An arithmetic operator has the wrong sign: a penalty is written as current_score + 5 instead of current_score - 5, often inside one branch of an if statement on attempt_number parity.

## Fix recipe
Flip the plus to a minus in the penalty branch so every wrong outcome deducts points consistently. Leave the win bonus formula unchanged.
