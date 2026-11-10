---
id: reversed-comparison
title: Reversed comparison operator
repair: flip_comparison_direction
---
# Reversed comparison operator

## Symptoms
check_guess returns "Too High" when the guess is lower than the secret and "Too Low" when it is higher. Every outcome label is wrong, not just the message text. Tests like test_guess_too_high or test_guess_too_low fail.

## Root cause
The comparison operator itself is reversed: guess < secret is used where guess > secret was intended.

## Fix recipe
Flip the comparison direction (< to >, or > to <) in the outcome check so the label matches the numeric relationship between guess and secret.
