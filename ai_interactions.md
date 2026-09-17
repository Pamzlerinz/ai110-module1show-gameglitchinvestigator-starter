# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agent Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

<!-- Describe the goal you asked the agent to accomplish -->

**What did the agent do?**

<!-- List the steps the agent took (files edited, commands run, etc.) -->

**What did you have to verify or fix manually?**

<!-- Describe anything the agent got wrong or that required human review -->

---

## Test Generation (SF7)

> Document how you used AI to help generate or improve tests.

**Prompt used:** "Look at `parse_guess` in `logic_utils.py`. Suggest three edge-case inputs that might still break the game (things like negative numbers, decimals, or extremely large values), and write pytest cases for each."

| Edge Case | Prompt Used | AI-Suggested Test | Did It Pass? | Your Reasoning |
|-----------|-------------|-------------------|--------------|----------------|
| Negative number (`"-5"`) | (above) | `test_parse_guess_accepts_negative_numbers` — asserts `parse_guess("-5")` returns `(True, -5, None)` | Yes | Nothing in `parse_guess` rejects a leading `-`, and the game never validates that a guess falls within the difficulty's range, so a negative guess should still parse cleanly as a valid (if unwinnable) guess rather than crash. |
| Non-numeric string (`"banana"`) | (above) | `test_parse_guess_rejects_non_numeric_string` — asserts it returns `(False, None, "That is not a number.")` | Yes | Users can type anything into a text box; this confirms the existing `try/except` around `int()`/`float()` actually catches garbage input gracefully instead of raising an uncaught exception that would crash the Streamlit app. |
| Extremely large number (`"99999999999999999999"`) | (above) | `test_parse_guess_accepts_very_large_numbers` — asserts it parses to the equivalent Python `int` | Yes | Python ints have arbitrary precision, but this is worth locking in as a test since a future refactor that swaps in a fixed-width numeric type (or adds range validation) could silently start overflowing or truncating on huge input. |
| Empty input (`""`) | (above, extended) | `test_parse_guess_rejects_empty_input` — asserts it returns `ok=False` with a non-empty error message | Yes | Covers the case of clicking "Submit Guess" without typing anything, which is an easy real-world mistake to make. |
| Decimal input (`"42.9"`) | (above, extended) | `test_parse_guess_accepts_decimal_strings` — asserts it truncates to `42` | Yes | The starter code has explicit `"." in raw` handling, so this locks in the truncation-not-rounding behavior on purpose. |

---

## Linting & Style (SF9)

> Document your use of AI for linting or code style improvements.

**Prompt used:**

```
<!-- Paste the prompt you gave the AI -->
```

**Linting output before:**

```
<!-- Paste relevant linter warnings/errors -->
```

**Changes applied:**

<!-- Describe what you changed based on the AI's suggestions -->

---

## Model Comparison (SF11)

> Compare two AI models on the same task.

**Task given to both models:**

<!-- Describe what you asked each model to do -->

| | Model A | Model B |
|-|---------|---------|
| **Model name** | | |
| **Response summary** | | |
| **More Pythonic?** | | |
| **Clearer explanation?** | | |

**Which did you prefer and why?**

<!-- Your conclusion -->
