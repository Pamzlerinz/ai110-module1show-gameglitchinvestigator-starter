# 🎮 Game Glitch Investigator: The Impossible Guesser

## 🚨 The Situation

You asked an AI to build a simple "Number Guessing Game" using Streamlit.
It wrote the code, ran away, and now the game is unplayable. 

- You can't win.
- The hints lie to you.
- The secret number seems to have commitment issues.

## 🛠️ Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Run the broken app: `python -m streamlit run app.py`

## 🕵️‍♂️ Your Mission

1. **Play the game.** Open the "Developer Debug Info" tab in the app to see the secret number. Try to win.
2. **Find the State Bug.** Why does the secret number change every time you click "Submit"? Ask ChatGPT: *"How do I keep a variable from resetting in Streamlit when I click a button?"*
3. **Fix the Logic.** The hints ("Higher/Lower") are wrong. Fix them.
4. **Refactor & Test.** - Move the logic into `logic_utils.py`.
   - Run `pytest` in your terminal.
   - Keep fixing until all tests pass!

## 📝 Document Your Experience

- [x] Describe the game's purpose.
- [x] Detail which bugs you found.
- [x] Explain what fixes you applied.

**Game purpose:** A Streamlit number-guessing game. The app picks a random secret number in a range set by the chosen difficulty (Easy 1-20, Normal 1-100, Hard 1-50), and the player has a limited number of attempts to guess it, getting a "Too High"/"Too Low" hint and a running score after each guess.

**Bugs found (see `reflection.md` for the full reproduction log):**

1. **Broken hints from a flip-flopping secret type** — `app.py` converted the secret to a `str` on every other attempt before comparing it to the (always-`int`) guess, which pushed `check_guess` into a `TypeError` fallback that compared numbers as strings (e.g. `"9" > "50"` is `True`). This made "Too High"/"Too Low" hints unreliable on top of bug #2 below.
2. **Hint direction was backwards** — the "Too High" outcome displayed "📈 Go HIGHER!" and "Too Low" displayed "📉 Go LOWER!" — exactly inverted. A guess that's too high should tell the player to go lower, and vice versa.
3. **"New Game" permanently stuck the game** — the New Game handler reset `attempts` and `secret` but never reset `status`, `score`, or `history`. After a single win or loss, `status` stayed `"won"`/`"lost"` forever, so every future rerun immediately hit the "game over" branch and `st.stop()` — the game could never actually restart.
4. **Score increased on wrong guesses** — `update_score`'s "Too High" branch awarded `+5` points instead of `-5` whenever the attempt number was even, so submitting a wrong guess could raise your score.
5. **Off-by-one in the attempts counter** — `attempts` was initialized to `1` instead of `0`, so the "Attempts left" display undercounted by one before the player had even guessed, and it shifted the win-score formula.
6. **Hardcoded range message** — the instructions always said "Guess a number between 1 and 100," even on Easy (1-20) or Hard (1-50).
7. **`check_guess` didn't match the starter tests** — it returned a `(outcome, message)` tuple, but `tests/test_game_logic.py` asserts a plain string result, so all three starter tests failed with `NotImplementedError` before anything was even moved into `logic_utils.py`.

**Fixes applied:** All game logic (`get_range_for_difficulty`, `parse_guess`, `check_guess`, `update_score`, plus a new `get_hint_message` helper) was moved into `logic_utils.py`, free of any Streamlit code. `check_guess` now always receives a plain `int` secret and returns only the outcome string, the hint messages point in the correct direction, `update_score` deducts points consistently for any wrong guess, "New Game" fully resets `status`/`score`/`history`/`secret` (using the correct difficulty range), `attempts` starts at `0`, and the range message uses the actual `low`/`high` for the selected difficulty. See the `# FIX:` comments in `app.py`/`logic_utils.py` and `reflection.md` for details on how each fix was verified.

## 📸 Demo Walkthrough

1. Player selects difficulty "Normal" (range 1-100, 8 attempts). The sidebar shows "Range: 1 to 100" and "Attempts allowed: 8".
2. The app secretly picks a number, e.g. `50`, and shows "Attempts left: 8" before any guess.
3. Player enters `40` and clicks "Submit Guess" → since `40 < 50`, the app shows "📈 Go HIGHER!" (Too Low) and the score drops by 5 (from 0 to -5).
4. Player enters `70` and clicks "Submit Guess" → since `70 > 50`, the app shows "📉 Go LOWER!" (Too High) and the score drops another 5 (to -10).
5. Player enters `50` and clicks "Submit Guess" → app shows "🎉 Correct!", balloons animate, and the status becomes "won" with a final score reflecting the win bonus.
6. Player clicks "New Game 🔁" → the secret, score (back to 0), attempts (back to 0), and status ("playing") all reset, and a brand-new round starts immediately instead of getting stuck on the old "You already won" screen.

## 🧪 Test Results

```
$ python -m pytest tests/ -v
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-9.1.1, pluggy-1.6.0
collected 14 items

tests/test_game_logic.py::test_winning_guess PASSED                      [  7%]
tests/test_game_logic.py::test_guess_too_high PASSED                     [ 14%]
tests/test_game_logic.py::test_guess_too_low PASSED                      [ 21%]
tests/test_game_logic.py::test_hint_direction_is_not_backwards PASSED    [ 28%]
tests/test_game_logic.py::test_too_high_always_deducts_points PASSED     [ 35%]
tests/test_game_logic.py::test_too_low_deducts_points PASSED             [ 42%]
tests/test_game_logic.py::test_win_score_uses_attempt_number_without_off_by_one PASSED [ 50%]
tests/test_game_logic.py::test_win_score_has_floor_of_ten PASSED         [ 57%]
tests/test_game_logic.py::test_parse_guess_rejects_empty_input PASSED    [ 64%]
tests/test_game_logic.py::test_parse_guess_rejects_non_numeric_string PASSED [ 71%]
tests/test_game_logic.py::test_parse_guess_accepts_negative_numbers PASSED [ 78%]
tests/test_game_logic.py::test_parse_guess_accepts_decimal_strings PASSED [ 85%]
tests/test_game_logic.py::test_parse_guess_accepts_very_large_numbers PASSED [ 92%]
tests/test_game_logic.py::test_range_for_easy_difficulty PASSED          [100%]

============================= 14 passed in 0.07s ==============================
```

## 🚀 Stretch Features

- [x] **Challenge 1: Advanced Edge-Case Testing.** Added pytest cases covering three edge-case inputs to `parse_guess`: a negative number (`"-5"`), a non-numeric string (`"banana"`), and an extremely large number (`"99999999999999999999"`), plus empty-input and decimal-input cases. All are included in the test run above (`test_parse_guess_*`). See `ai_interactions.md` for the prompts used and the reasoning behind each edge case.
