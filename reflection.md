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

---

## 2. How did you use AI as a teammate?

- Which AI tools did you use on this project (for example: ChatGPT, Gemini, Copilot)?
- Give one example of an AI suggestion that was correct (including what the AI suggested and how you verified the result).
- Give one example of an AI suggestion you did not accept as written (including what the AI suggested, why you rejected or changed it, and how you verified your version). It does not have to be a suggestion that was wrong: over-engineered, out of scope, harder to read, or a poor fit for this codebase all count.

---

## 3. Debugging and testing your fixes

- How did you decide whether a bug was really fixed?
- Describe at least one test you ran (manual or using pytest)  
  and what it showed you about your code.
- Did AI help you design or understand any tests? How?

---

## 4. What did you learn about Streamlit and state?

- How would you explain Streamlit "reruns" and session state to a friend who has never used Streamlit?

---

## 5. Looking ahead: your developer habits

- What is one habit or strategy from this project that you want to reuse in future labs or projects?
  - This could be a testing habit, a prompting strategy, or a way you used Git.
- What is one thing you would do differently next time you work with AI on a coding task?
- In one or two sentences, describe how this project changed the way you think about AI generated code.
