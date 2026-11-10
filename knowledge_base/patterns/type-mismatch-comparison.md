---
id: type-mismatch-comparison
title: Type mismatch in comparison (str vs int)
repair: remove_str_cast
---
# Type mismatch in comparison (str vs int)

## Symptoms
Hints are correct on some attempts and wrong on others, often alternating every other guess. A guess of 9 against a secret of 50 says "Too High". Tests comparing guess and secret fail only for certain attempt numbers. The secret number seems to change type or have commitment issues.

## Root cause
One side of the comparison is converted to a string with str() before comparing with an integer. In Python 3 comparing int and str raises TypeError, and a fallback that converts both to strings compares them lexicographically, so "9" > "50" is True.

## Fix recipe
Remove the str() cast so both values stay integers before comparison. Keep the secret stored as a plain int in state. If a TypeError fallback exists it should never be reached once types are consistent.
