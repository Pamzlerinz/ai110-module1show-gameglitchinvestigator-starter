---
id: case-history
title: Case history from the original Game Glitch Investigator (Module 1)
---
# Case history: bugs found and fixed by hand in Module 1

Each entry is a real bug from the original project's bug reproduction log
(`reflection.md`). The `pattern:` line links the entry to a pattern document so
the agent can reuse the fix recipe.

### Guess of 9 said "Too High" against a secret of 50
pattern: type-mismatch-comparison
Hints were right on odd attempts and wrong on even ones. app.py did
secret = str(st.session_state.secret) on every other attempt, so check_guess
compared an int guess with a str secret, hit the TypeError fallback, and compared
strings: "9" > "50" is True. Fixed by passing the plain int secret every time.
Verified by repeating guess 9 vs secret 50 across many attempts.

### Hint said "Go HIGHER" when the guess was too high
pattern: inverted-hint
The HINT_MESSAGES dictionary mapped "Too High" to "📈 Go HIGHER!" and "Too Low"
to "📉 Go LOWER!", exactly backwards. The outcome labels were correct, only the
message text and arrows were swapped. Regression test:
test_hint_direction_is_not_backwards.

### New Game left the player stuck on "You already won"
pattern: incomplete-state-reset
The New Game handler reset attempts and secret but never status, score, or
history. The stale status kept triggering st.stop(), so a second round could
never start. Fixed by resetting every key the initial state defines.

### Score went up after a wrong guess on even attempts
pattern: score-sign-error
update_score's "Too High" branch did current_score + 5 when attempt_number was
even. A wrong guess should always deduct. Regression test:
test_too_high_always_deducts_points expects 100 -> 95 on attempts 2 and 3.

### Attempts left was one short before the first guess
pattern: off-by-one-counter
st.session_state.attempts was initialized to 1 instead of 0, so "Attempts left"
showed 7 on Normal (limit 8) before any guess, and the win score formula was
shifted by one attempt.

### Instructions always said 1 to 100
pattern: hardcoded-range-message
The info message was a literal string "Guess a number between 1 and 100" even on
Easy and Hard. Fixed by formatting it with low and high from
get_range_for_difficulty.
