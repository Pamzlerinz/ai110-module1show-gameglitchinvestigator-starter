---
id: exclusive-boundary
title: Exclusive boundary check rejects valid edge values
repair: fix_comparison_boundary
---
# Exclusive boundary check rejects valid edge values

## Symptoms
Guesses equal to the lowest or highest number in the range are rejected as invalid or out of range. Guessing 1 or 20 on Easy fails validation even though the range is 1 to 20. Tests like test_low_boundary_is_valid or test_high_boundary_is_valid fail.

## Root cause
A range check uses strict comparison (low < guess < high) when the range is meant to be inclusive.

## Fix recipe
Change < to <= (and > to >=) on the boundary comparison so both endpoints are accepted: low <= guess <= high.
