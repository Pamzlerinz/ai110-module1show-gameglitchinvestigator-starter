---
id: hardcoded-range-message
title: Hardcoded range in user-facing text
repair: none
---
# Hardcoded range in user-facing text

## Symptoms
The instructions always say "Guess a number between 1 and 100" even on Easy (1 to 20) or Hard (1 to 50). The message does not match the selected difficulty.

## Root cause
The prompt string has literal numbers instead of using the low and high values returned by get_range_for_difficulty.

## Fix recipe
Build the message with an f-string from the actual low and high values for the current difficulty. Review by hand: this is a text change that tests rarely cover.
