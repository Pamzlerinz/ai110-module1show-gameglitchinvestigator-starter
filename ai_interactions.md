# AI Interactions Log

This file has two parts:

1. **Final project (Agentic Workflow Enhancement):** intermediate reasoning traces from the Glitch Investigator agent. They show its plan, tool calls (test runs, retrieval), decisions, and self-checks.
2. **Module 1 (original project):** the AI-assisted test-generation log from the original Game Glitch Investigator.

---

# Part 1: Agent reasoning traces

Each agent run records a step-by-step trace. The steps are `plan → validate → observe → retrieve → propose → verify/reject → accept → (repeat) → report`, and the trace is saved as JSON. The committed traces live in [assets/traces/](assets/traces/): one per evaluation case and retrieval configuration, for example `08_multi_bug__rag_full.json`. The readable versions below come from `python investigate.py ... --trace`.

How to read a trace:

| Action | What the agent is doing |
|---|---|
| `plan` | States the plan, backend, and whether retrieval is on |
| `validate` / `refuse` | Input guardrails (dangerous imports, unparseable code, tests that don't import the target) |
| `observe` | **Tool call:** runs the test suite in the sandbox and records what fails |
| `retrieve` | **Tool call:** BM25 search over the knowledge base, using the symptom + the *current* failures as the query |
| `propose` | Generates candidate patches from the retrieved patterns (offline) or asks Claude |
| `verify` / `reject` | **Self-check:** each candidate goes through the patch guardrails, then the tests; regressions are discarded |
| `accept` | Decision: keeps the best non-regressing candidate, then loops on what still fails |
| `report` | Final status + confidence; a human decides whether to apply |

## Trace A: three overlapping bugs, solved in three planning iterations (full RAG)

Case `eval/cases/08_multi_bug`: the original Module 1 glitches combined. Notice that retrieval is **re-run every iteration** with the remaining failures, so the ranking of patterns changes as bugs are fixed. Notice also the self-checks: candidates that regress a passing test (steps 18, 20, 25, 26) and a no-op patch (step 17) are rejected.

```text
$ python investigate.py eval/cases/08_multi_bug/game.py --tests eval/cases/08_multi_bug/test_game.py --symptom "The original glitchy game: hints lie, score goes up when I am wrong, and 9 vs 50 says Too High." --trace
--- agent trace -----------------------------------------------------
   1. plan     backend=offline-heuristic retrieval=True plan: validate input -> run tests -> retrieve bug patterns -> propose patches -> guardrail-check + verify each patch -> iterate on remaining failures -> score confidence and report for human approval
   2. validate ok=True
   3. observe  tests 0/3 passed; failing: test_hint_direction, test_even_attempt_low_guess, test_wrong_guess_lowers_score
   4. retrieve top chunks: patterns:score-sign-error (24.28); patterns:inverted-hint (23.47); patterns:inverted-hint (19.51); case_history:score-sign-error (18.21) => patterns: score-sign-error (1.0), inverted-hint (0.967), type-mismatch-comparison (0.673)
   5. propose  iteration 1: 6 candidate patch(es)
   6. verify   [score-sign-error] change `state["attempts"] += 1` to `state["attempts"] -= 1` => 0/3 passed
   7. verify   [score-sign-error] change `state["score"] + 5` to `state["score"] - 5` => 1/3 passed
   8. verify   [score-sign-error] change `state["score"] - 5` to `state["score"] + 5` => 0/3 passed
   9. verify   [inverted-hint] swap HIGHER/LOWER wording in 2 string literal(s) => 1/3 passed
  10. verify   [type-mismatch-comparison] remove `secret = str(secret)` (and its `if state["attempts"] % 2 == 0` guard) => 1/3 passed
  11. verify   [type-mismatch-comparison] replace str(guess) with guess => 0/3 passed
  12. accept   iteration 1: keep [score-sign-error] change `state["score"] + 5` to `state["score"] - 5` (1/3 passed)
  13. retrieve top chunks: patterns:inverted-hint (18.08); patterns:inverted-hint (17.78); patterns:score-sign-error (16.97); case_history:inverted-hint (14.1) => patterns: inverted-hint (1.0), score-sign-error (0.939), type-mismatch-comparison (0.772)
  14. propose  iteration 2: 6 candidate patch(es)
  15. verify   [inverted-hint] swap HIGHER/LOWER wording in 2 string literal(s) => 2/3 passed
  16. verify   [score-sign-error] change `state["attempts"] += 1` to `state["attempts"] -= 1` => 1/3 passed
  17. reject   change `state["score"] - 5` to `state["score"] + 5` => rejected: patch makes no change
  18. verify   [score-sign-error] change `state["score"] - 5` to `state["score"] + 5` => regression: test_wrong_guess_lowers_score
  19. verify   [type-mismatch-comparison] remove `secret = str(secret)` (and its `if state["attempts"] % 2 == 0` guard) => 2/3 passed
  20. verify   [type-mismatch-comparison] replace str(guess) with guess => regression: test_wrong_guess_lowers_score
  21. accept   iteration 2: keep [inverted-hint] swap HIGHER/LOWER wording in 2 string literal(s) (2/3 passed)
  22. retrieve top chunks: patterns:score-sign-error (15.22); case_history:score-sign-error (13.2); patterns:type-mismatch-comparison (12.49); case_history:type-mismatch-comparison (11.32) => patterns: score-sign-error (1.0), type-mismatch-comparison (0.821), inverted-hint (0.736)
  23. propose  iteration 3: 6 candidate patch(es)
  24. verify   [score-sign-error] change `state["attempts"] += 1` to `state["attempts"] -= 1` => 2/3 passed
  25. verify   [score-sign-error] change `state["score"] - 5` to `state["score"] + 5` => regression: test_wrong_guess_lowers_score
  26. verify   [score-sign-error] change `state["score"] - 5` to `state["score"] + 5` => regression: test_wrong_guess_lowers_score
  27. verify   [type-mismatch-comparison] remove `secret = str(secret)` (and its `if state["attempts"] % 2 == 0` guard) => 3/3 passed
  28. accept   iteration 3: keep [type-mismatch-comparison] remove `secret = str(secret)` (and its `if state["attempts"] % 2 == 0` guard) (3/3 passed)
  29. report   status=fixed, confidence=0.95, message=All tests pass after 3 verified change(s).
```

JSON: [assets/traces/08_multi_bug__rag_full.json](assets/traces/08_multi_bug__rag_full.json)

## Trace B: the same case without the case-history source (a wrong-but-green fix)

With only the pattern documents indexed, a fourth pattern (`reversed-comparison`) is retrieved. Its candidate in step 13 makes 2/3 tests pass at once, so the greedy decision in step 14 keeps it. The final patch passes every test, but the actual `str()` bug is still there. This is the key reliability finding discussed in [model_card.md](model_card.md).

```text
status=fixed confidence=0.88 patterns_used=['reversed-comparison', 'inverted-hint']
   1. plan     backend=offline-heuristic retrieval=True plan: validate input -> run tests -> retrieve bug patterns -> propose patches -> guardrail-check + verify each patch -> iterate on remaining failures -> score confidence and report for human approval
   2. validate ok=True
   3. observe  tests 0/3 passed; failing: test_hint_direction, test_even_attempt_low_guess, test_wrong_guess_lowers_score
   4. retrieve top chunks: patterns:score-sign-error (25.59); patterns:inverted-hint (24.6); patterns:inverted-hint (19.71); patterns:type-mismatch-comparison (17.13) => patterns: score-sign-error (1.0), inverted-hint (0.961), type-mismatch-comparison (0.669), reversed-comparison (0.591)
   5. propose  iteration 1: 8 candidate patch(es)
   6. verify   [score-sign-error] change `state["attempts"] += 1` to `state["attempts"] -= 1` => 0/3 passed
   7. verify   [score-sign-error] change `state["score"] + 5` to `state["score"] - 5` => 1/3 passed
   8. verify   [score-sign-error] change `state["score"] - 5` to `state["score"] + 5` => 0/3 passed
   9. verify   [inverted-hint] swap HIGHER/LOWER wording in 2 string literal(s) => 1/3 passed
  10. verify   [type-mismatch-comparison] remove `secret = str(secret)` (and its `if state["attempts"] % 2 == 0` guard) => 1/3 passed
  11. verify   [type-mismatch-comparison] replace str(guess) with guess => 0/3 passed
  12. verify   [reversed-comparison] change `>` to `<` in `guess > secret` => 1/3 passed
  13. verify   [reversed-comparison] change `>` to `<` in `g > secret` => 2/3 passed
  14. accept   iteration 1: keep [reversed-comparison] change `>` to `<` in `g > secret` (2/3 passed)
  15. retrieve top chunks: patterns:inverted-hint (16.99); patterns:inverted-hint (16.78); patterns:score-sign-error (13.36); patterns:type-mismatch-comparison (11.71) => patterns: inverted-hint (1.0), score-sign-error (0.786), type-mismatch-comparison (0.689), reversed-comparison (0.417)
  16. propose  iteration 2: 8 candidate patch(es)
  17. verify   [inverted-hint] swap HIGHER/LOWER wording in 2 string literal(s) => 3/3 passed
  18. accept   iteration 2: keep [inverted-hint] swap HIGHER/LOWER wording in 2 string literal(s) (3/3 passed)
  19. report   status=fixed, confidence=0.88, message=All tests pass after 2 verified change(s).
--- a/game.py
+++ b/game.py
@@ -1,4 +1,4 @@
-HINT_MESSAGES = {"Win": "🎉 Correct!", "Too High": "📈 Go HIGHER!", "Too Low": "📉 Go LOWER!"}
+HINT_MESSAGES = {"Win": "🎉 Correct!", "Too High": "📉 Go LOWER!", "Too Low": "📈 Go HIGHER!"}
 
 
 def check_guess(guess, secret):
@@ -12,7 +12,7 @@
         g = str(guess)
         if g == secret:
             return "Win"
-        if g > secret:
+        if g < secret:
             return "Too High"
         return "Too Low"
```

JSON: [assets/traces/08_multi_bug__rag_patterns_only.json](assets/traces/08_multi_bug__rag_patterns_only.json)

## Trace C: knowing when to stop

Case `11_missing_feature`: the tests ask for a feature that doesn't exist yet. Retrieval finds only loosely related patterns, none of their repairs apply, and the agent stops and escalates instead of guessing.

```text
--- agent trace -----------------------------------------------------
   1. plan     backend=offline-heuristic retrieval=True plan: validate input -> run tests -> retrieve bug patterns -> propose patches -> guardrail-check + verify each patch -> iterate on remaining failures -> score confidence and report for human approval
   2. validate ok=True
   3. observe  tests 2/3 passed; failing: test_very_close_hint
   4. retrieve top chunks: patterns:inverted-hint (7.09); case_history:inverted-hint (6.62); patterns:type-mismatch-comparison (5.98); case_history:type-mismatch-comparison (5.64) => patterns: inverted-hint (1.0), type-mismatch-comparison (0.844)
   5. propose  iteration 1: 0 candidate patch(es)
   6. stuck    reason=no candidate improved the test results without regressions
   7. report   status=needs_human_review, confidence=0.0, message=No verified fix. The failing tests do not match any repair the agent could confirm; a human should investigate.
```

## Trace D: the Claude backend's request

When `ANTHROPIC_API_KEY` is set, the `propose` step sends Claude a prompt built by `ClaudeBackend.build_prompt` (see `glitch_agent/backends.py`). It contains the symptom, the failing tests, the **retrieved knowledge-base chunks**, the earlier attempts from this session (so a retry can learn from a failed patch), and the module source. Claude answers with schema-constrained JSON (`diagnosis`, `pattern_id`, `confidence`, `patched_source`). That answer then goes through the same guardrails and test verification as any offline candidate. `tests/test_agent.py` covers this path with a fake client (checking that retrieved text is in the prompt, that an unsafe patch is rejected, and that an API failure falls back to the offline planner). No live Claude trace is committed, because no API key was available when the evidence was generated.

---

# Part 2: Module 1 (original project)

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
