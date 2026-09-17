# 💭 Reflection: Game Glitch Investigator

Answer each question in 3 to 5 sentences. Be specific and honest about what actually happened while you worked. This is about your process, not trying to sound perfect.

## 1. What was broken when you started?

The first time I ran the game it looked fine on the surface — a title, a difficulty picker, a text box, and a "Submit Guess" button — but playing it a few rounds exposed several real problems. The hints ("Go HIGHER!"/"Go LOWER!") were sometimes flat-out wrong for the number I typed, the score would occasionally go up after a wrong guess instead of down, and once I won or ran out of attempts, clicking "New Game" looked like it reset the board but then immediately locked me back into the "Game over" screen, so I could never actually play a second round. Running `pytest` from the start also failed all three starter tests with `NotImplementedError`, since `logic_utils.py` was just stub functions that nothing had been moved into yet.

**Bug Reproduction Log**

| Input | Expected Behavior | Actual Behavior | Console Output / Error |
|-------|-------------------|-----------------|------------------------|
| Guess of 9 when secret was 50 | "Too Low" hint | "Too High" hint shown on some attempts | none (silent logic bug — secret alternates between `int` and `str` every other attempt, so the comparison falls back to lexicographic string comparison, e.g. `"9" > "50"` is `True`) |
| Click "New Game" after winning | Board resets and a new round starts | "You already won. Start a new game to play again." is shown again and the app calls `st.stop()`, so the game is permanently stuck | none (silent — `status` is never reset to `"playing"` in the New Game handler) |
| Guess of 60 when secret was 50, submitted on an even attempt number | Score decreases by 5 for a wrong "Too High" guess | Score increases by 5 instead | none (silent — `update_score`'s "Too High" branch adds points when `attempt_number % 2 == 0`) |
| Run `pytest tests/` from a fresh clone | All 3 starter tests pass | All 3 tests fail | `NotImplementedError: Refactor this function from app.py into logic_utils.py` |
| Guess of 60 when secret was 50 | Hint tells the player to go LOWER (since 60 is too high) | Hint said "📈 Go HIGHER!" | none (silent — the `HINT_MESSAGES`/return values for "Too High" and "Too Low" were swapped, so the direction was backwards for every guess, independent of the int/str bug above) |

---

## 2. How did you use AI as a teammate?

I used Claude (Claude Code, in VS Code) as my AI coding assistant for this whole project.

**A correct suggestion:** I described the hint bug ("guess of 9 against a secret of 50 sometimes says Too High") and asked Claude to explain the underlying logic. It traced the flow through `app.py` and pointed out that on even attempt numbers the code did `secret = str(st.session_state.secret)` before calling `check_guess(guess_int, secret)`, so an `int` guess was being compared to a `str` secret. In Python 3 that raises `TypeError` on `>`, which `check_guess`'s `except TypeError` branch quietly caught by converting the guess to a string too and comparing lexicographically — so `"9" > "50"` evaluates `True` because `"9"` sorts after `"5"` character-by-character. That explanation was correct: I verified it by removing the `str()` conversion in app.py and confirming the same guess (9 vs 50) reliably showed "Too Low" across many attempts, both in the running app and in `check_guess(9, 50) == "Too Low"` at a Python prompt.

**A suggestion I didn't accept as written:** When I asked Claude to fix the `check_guess` function, its first draft kept the original return shape of `(outcome, message)` — a tuple of the result and the display string. That's a reasonable design on its own, but it conflicted with the starter tests in `tests/test_game_logic.py`, which already assert `check_guess(50, 50) == "Win"` (a plain string). Keeping the tuple would have meant either rewriting the given tests (which the instructions didn't ask me to do) or living with tests that fail even after the "fix." Instead I asked Claude to change `check_guess` to return only the outcome string and move the message lookup into a small `get_hint_message(outcome)` helper that `app.py` calls separately. I verified this version by running `pytest`, which passed the original three starter tests unmodified, and by confirming the hint text still displayed correctly in the running app.

---

## 3. Debugging and testing your fixes

I considered a bug "really fixed" only when two things were both true: the automated tests passed, and I could no longer reproduce the original symptom by hand in the running app for several different inputs (not just the one example from the bug log). For the scoring bug, I ran the app, deliberately submitted "Too High" guesses on both even and odd attempt numbers, and confirmed the score dropped by 5 every time instead of increasing on even attempts. For the "New Game" bug, I played a full game to a win, clicked "New Game," and confirmed I got a fresh round instead of being stuck on the "You already won" screen. On the automated side, I ran `pytest tests/test_game_logic.py -v` after each fix; before the refactor all three starter tests failed with `NotImplementedError` (since `logic_utils.py` was still stubs), and after moving the real logic in and fixing the identified bugs, all 14 tests (3 starter + 11 new) passed. AI helped me design the new tests: I described each bug and asked Claude to suggest a regression test for it (for example, "write a test that would have caught the Too-High scoring bug"), and it proposed asserting `update_score(100, "Too High", attempt_number=2) == 95`, which directly encodes the fixed behavior and would fail again if the bug ever came back.

---

## 4. What did you learn about Streamlit and state?

Streamlit doesn't run like a normal desktop or web app that waits and reacts to individual events — instead, every time you click a button or type in a box, Streamlit throws away the current run and re-executes the *entire* script from top to bottom, like restarting the file. That's why plain Python variables are useless for remembering anything between clicks: a variable like `attempts = 0` written directly in the script would just get reset to `0` on every rerun. `st.session_state` is Streamlit's workaround — it's a dictionary-like object that survives across reruns for the same browser session, so anything you truly want to persist (the secret number, the score, how many attempts have been used) has to live there instead of in a normal variable. This project's "New Game" bug was a great illustration of that: it's not enough to reset *some* of the session state keys, because whatever you forget (like `status`) will still be sitting there on the next rerun as if nothing happened.

---

## 5. Looking ahead: your developer habits

One habit I want to keep is writing a small regression test *immediately* after fixing a bug, using the exact numbers from the bug report, before moving on to the next issue — it turns "I think this is fixed" into something checkable, and it means the bug can never silently come back without a test failing. One thing I'd do differently next time is ask the AI for its reasoning *before* accepting a code change, rather than after — for the `check_guess` return-type issue, I could have caught the tuple-vs-string mismatch sooner if I'd asked "will this still satisfy the existing tests?" as part of the original prompt instead of noticing the conflict after the fact. Overall, this project changed how I think about AI-generated code: it can look complete and even syntactically correct while quietly contradicting its own tests or mixing incompatible ideas (like a secret number that's sometimes an int and sometimes a string), so I can't treat "the AI wrote it" as equivalent to "it works" — I have to actually run it, play with it, and read the diff line by line.
