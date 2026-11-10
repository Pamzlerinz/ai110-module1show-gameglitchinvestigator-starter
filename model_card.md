# Model Card: Glitch Investigator Agent

## Overview

| | |
|---|---|
| **System** | Glitch Investigator: a retrieval-augmented debugging agent for small Python game modules |
| **Base project** | *Game Glitch Investigator* (AI110 Module 1) |
| **Task** | Given a buggy module, its pytest file and a plain-language symptom, diagnose the bug, propose a minimal patch, verify it against the tests, and report a confidence score for human review |
| **AI features** | Retrieval-Augmented Generation (BM25 over a bug-pattern knowledge base + the Module 1 case history), an agentic plan → act → verify loop, guardrails, and an evaluation harness |
| **Reasoning backends** | `claude-opus-5-5` through the Anthropic SDK (structured JSON output) when `ANTHROPIC_API_KEY` is set; otherwise a deterministic offline planner that applies the repair recipe of each retrieved pattern |
| **Intended users** | Students and hobby developers debugging small, well-tested Python modules |
| **Not intended for** | Production code, large codebases, untrusted code, or code without tests |

## How it decides

1. **Input guardrails** refuse empty, oversized, or unparseable files. They also refuse any file that imports `os`/`subprocess`/`socket`/... or calls `eval`/`exec`/`open`, and test files that never import the target. These checks run before any code executes.
2. **Observe.** It runs the tests in a temp-dir sandbox (pytest subprocess, 30 s timeout). If everything already passes, it reports `no_bug_detected` and changes nothing.
3. **Retrieve.** It builds a query from the symptom plus the failing test names and assertion messages, then ranks knowledge-base chunks with BM25. It collapses those chunks into a ranked list of patterns, each with a normalised *support* score.
4. **Propose.** The offline planner runs only the repair strategies of retrieved patterns; Claude receives the retrieved text, the failures, and any earlier failed attempts.
5. **Patch guardrails** reject candidates that don't parse, add banned operations, delete functions, or change more than 20 lines.
6. **Verify.** Each candidate runs against the unmodified tests. Any candidate that breaks a previously passing test is discarded. The best improving candidate is kept, then the loop goes back to step 3 for whatever still fails (max 4 iterations, 40 candidates).
7. **Confidence** = `0.55 × test pass ratio + 0.30 × retrieval support of the weakest pattern used + 0.15 × patch minimality`. With Claude, this is blended 70/30 with the model's self-rated confidence. Only results at or above **0.75** with all tests green are labelled `fixed`. Everything else is `partial` or `needs_human_review`.
8. **Human in the loop.** The agent never edits the user's file on its own. The CLI writes a fix only with `--apply` and keeps a `.bak` backup. The Streamlit page only offers a download.

## Evaluation results

Run with `python evaluate.py --compare` (offline backend, deterministic). Full table: [eval/results.md](eval/results.md). Raw log: [assets/sample_runs/evaluate_compare.txt](assets/sample_runs/evaluate_compare.txt).

| Config | Cases passed | Tests made green | Auto-accepted | Green but **wrong-pattern** patches | Avg candidates tested |
|---|---|---|---|---|---|
| Full RAG (patterns + case history) | **11/11** | 8/8 | 8/8 | **0** | 4.1 |
| RAG, pattern docs only | 10/11 | 8/8 | 8/8 | 1 | 3.4 |
| No retrieval (blind search over all repairs) | 3/11 | 8/8 | 0/8 | 2 | 10.6 |

The 11 cases cover 7 single-bug cases, 1 three-bug case (the original Module 1 glitches combined), an already-correct module (the fixed Module 1 `logic_utils.py`), a dangerous input that must be refused, and a requested feature that the agent should not invent (it must hand that one to a human). There are also 39 pytest tests: unit tests for retrieval, repairs, and guardrails; end-to-end agent runs; and Claude-backend tests that use a fake client, so they need no network.

## Limitations and biases

- **Narrow pattern coverage.** The offline planner can only fix the 8 bug shapes that have a repair strategy. Anything else, like missing features, wrong formulas, or UI-only Streamlit bugs, ends as `needs_human_review`. That is the intended failure mode, but it means many real bugs go unfixed.
- **Only as good as the tests.** "Verified" means "the provided tests pass". A weak test suite can be satisfied by a wrong patch (see *What surprised me*). The agent cannot detect bugs the tests don't cover.
- **Knowledge-base bias.** The knowledge base was written from one project's bugs, a number-guessing game. Its vocabulary ("hint", "secret", "attempt", "score") biases retrieval toward those bugs. A symptom described in different words, or in another language, retrieves worse. BM25 has no notion of synonyms.
- **Greedy search.** Each iteration keeps the candidate that turns the most tests green. That candidate can be the wrong one when several fixes overlap, which is exactly what happened in the patterns-only ablation.
- **Confidence is a heuristic, not a calibrated probability.** The weights were chosen by hand and checked on 11 cases. That is far too few to claim calibration.
- **Claude backend not exercised in the committed evidence.** The committed results use the offline backend because no API key was available when they were generated. The Claude path is covered by tests with a fake client, but its real-world accuracy has not been measured here.
- **The sandbox is not a security boundary.** It isolates the user's files, not the machine. The static banned-import check is a coarse filter that a determined attacker could get around (for example with `getattr` tricks).

## Future improvements

Each item below answers one of the limitations above.

- **Measure the Claude backend for real.** Run `evaluate.py` with an API key and compare Claude against the offline planner on the same 11 cases, including how often its self-rated confidence matches the verified outcome.
- **Retrieval that understands synonyms.** Add embedding search next to BM25 (hybrid retrieval), so a symptom like "points went the wrong way" still finds the score-sign pattern.
- **Prefer the better-explained fix.** Instead of greedily keeping the candidate that turns the most tests green, score candidates by tests *and* retrieval support together, which would have avoided the wrong-but-green patch in the patterns-only run.
- **Catch weak test suites.** Use mutation testing to check whether the user's tests can tell a correct patch from an overfitted one, and warn when they can't.
- **More repair strategies and a bigger evaluation set.** Cover more bug shapes than the current 8, and grow the 11 cases so the confidence weights can be checked properly.
- **A real sandbox.** Run candidate tests in a container with no network or file access outside the temp dir, instead of relying on the static banned-import check.

## Misuse and prevention

| Possible misuse | Mitigation in this system |
|---|---|
| Submitting malicious code to get it executed (the agent runs tests) | Static refusal of dangerous imports and calls before any execution; temp-dir isolation; 30 s timeout. Documented as *not* a security sandbox: only run it on code you would run yourself. |
| "Fixing" code by weakening the tests | The agent never modifies the test file. It is copied unmodified into every sandbox run. |
| Trusting an AI patch blindly | No automatic writes; confidence threshold; `needs_human_review` status; full JSON trace of every candidate tried and why it was kept or rejected. |
| Generating large rewrites that hide behaviour changes | Patch guardrail caps changes at 20 lines and forbids deleting definitions. |
| Prompt injection through code comments (Claude backend) | Claude's output is never executed directly. It must pass the same patch guardrails and the tests, and it can only replace the target module. |

## What surprised me while testing reliability

The biggest surprise was a **patch that passed every test and was still wrong**. With only the pattern documents indexed, the agent "fixed" the three-bug case by flipping `>` to `<` inside the string-comparison fallback of `check_guess`. That change happened to make all three tests pass. The real bug, a `str()` cast on the secret, was still there. Blind search found that same wrong patch, plus a second one. On the type-mismatch case, blind search changed `if attempt_number % 2 == 0:` to `% 3 == 0`. That patch simply avoids the attempt numbers the tests happen to use (1, 2, 4), so the tests pass while the `str()` bug still fires on attempt 3. It is textbook overfitting to a test suite, produced by an automated search with no understanding of the bug. The confidence score (0.88) did not catch it either. The evaluator caught it only because it checks *which pattern* explains the fix, not just whether the tests are green. Adding the Module 1 case history as a second retrieval source filled the top results with chunks about the real bugs, so "reversed comparison" was never retrieved. It surfaced the real story instead: "guess of 9 said Too High against 50 because of `str()`". The agent then made the correct fix.

Two lessons came out of it. First, a green test suite is necessary but not sufficient evidence. Second, retrieval is a source of *justification* as much as of ideas. Blind search made the tests pass in 8/8 cases, but with no retrieved evidence its confidence stayed at 0.70. It never crossed the auto-accept threshold, which is the behaviour I want.

A smaller surprise was the tokenizer bug my own unit test caught. It stripped plurals *after* removing stopwords, so "games" slipped past the stopword filter as "game".

## Collaboration with AI during this project

This extension was built with Claude (Claude Code in VS Code) as a pair programmer. The starting point was the goal: turn the Module 1 bug-hunt into an agent that does the hunting. The assignment's requirements set the constraints. Claude proposed the architecture, wrote first drafts, and ran the tests and evaluation. Every change was checked against the test suite, the evaluation table, and the agent traces before it was kept.

**A suggestion that was accepted:** support *two* reasoning backends behind one interface. Claude handles diagnosis when an API key is present. Otherwise a deterministic offline planner applies the repair recipes of the retrieved patterns. It was accepted for two reasons. It makes the project reproducible for a grader or employer with no API key and no cost. It also makes retrieval measurable: with the offline planner, the ablation shows exactly how much the knowledge base changes the outcome (11/11 vs 3/11 cases).

**Suggestions that were not kept as written:**
- *A misleading evaluation summary.* The first version of `evaluate.py` reported the no-retrieval ablation as "fixed 0/8". That made retrieval look like the only way to get passing tests, which is false: blind search made the tests green in 8/8 cases. Retrieval's real contribution is justification, efficiency (4.1 vs 10.6 candidates), and avoiding a wrong patch. The summary was changed to report "tests made green", "auto-accepted", and "green but wrong-pattern patches" separately, because the honest version is also the more interesting result.
- *A repair that left dead code.* The first `remove_str_cast` turned `secret = str(secret)` into `secret = secret` inside an `if` block. The tests passed, but no human would write that line. The repair now removes the whole guarded block in that situation.
- *An unreadable metric.* One draft computed "tests green" by string-slicing the `"3/4 passed -> 4/4 passed"` summary. It was replaced by a boolean stored with each result.

## Testing summary

- `python -m pytest`: 39 tests, all passing (15 game-logic tests + 24 agent tests).
- `python evaluate.py --compare`: 11/11 cases pass with full RAG. Average confidence on accepted fixes is 0.99. Retrieval hit@1 is 8/8 and recall is 1.0 on the fixable cases.
- What didn't work: the patterns-only configuration produced a wrong-but-green patch on the three-bug case, and blind search produced two. The greedy search has no way to prefer the fix that is better *explained*, so I rely on retrieval and the human-review threshold to catch this.
