"""Unit and integration tests for the Glitch Investigator agent."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from glitch_agent import repairs
from glitch_agent.agent import GlitchAgent
from glitch_agent.backends import BackendError, ClaudeBackend, HeuristicBackend
from glitch_agent.guardrails import GuardrailViolation, validate_inputs, validate_patch
from glitch_agent.retriever import Retriever, rank_patterns, tokenize

CASES = Path(__file__).resolve().parent.parent / "eval" / "cases"


# --- retrieval ---------------------------------------------------------------

def test_tokenize_splits_snake_case_and_plurals():
    assert tokenize("test_history_not_shared_between_games") == ["history", "not", "shared", "between"]


@pytest.mark.parametrize("query, expected", [
    ("hint says go higher when my guess was too high", "inverted-hint"),
    ("score went up after a wrong guess", "score-sign-error"),
    ("9 vs 50 says Too High only on some attempts", "type-mismatch-comparison"),
    ("New Game is stuck on You already won", "incomplete-state-reset"),
    ("history from last game shows up in new game", "mutable-default-argument"),
])
def test_retrieval_ranks_expected_pattern_first(query, expected):
    ranked = rank_patterns(Retriever.from_kb().search(query))
    assert ranked[0][0] == expected


def test_case_history_source_is_indexed():
    sources = {c.source for c in Retriever.from_kb().chunks}
    assert sources == {"patterns", "case_history"}


# --- repair strategies -------------------------------------------------------

def test_swap_direction_words_only_touches_strings():
    src = 'HIGHER = 1\nMSG = {"Too High": "📈 Go HIGHER!"}\n'
    (cand,) = repairs.generate("swap_direction_words", src)
    assert cand.source == 'HIGHER = 1\nMSG = {"Too High": "📉 Go LOWER!"}\n'


def test_remove_str_cast_drops_self_assignment_guard():
    src = "def f(s, n):\n    if n % 2 == 0:\n        s = str(s)\n    return s\n"
    (cand,) = repairs.generate("remove_str_cast", src)
    assert "str(" not in cand.source and "if n" not in cand.source


def test_mutable_default_fix():
    src = 'def record(g, history=[]):\n    """doc"""\n    history.append(g)\n    return history\n'
    (cand,) = repairs.generate("fix_mutable_default", src)
    ns = {}
    exec(cand.source, ns)
    assert ns["record"](1) == [1] and ns["record"](2) == [2]


def test_complete_state_reset_adds_missing_keys():
    src = ('def new():\n    return {"a": 0, "status": "playing"}\n\n'
           'def reset_game(s):\n    s["a"] = 0\n    return s\n')
    (cand,) = repairs.generate("complete_state_reset", src)
    assert 's["status"] = "playing"' in cand.source


def test_unknown_strategy_yields_nothing():
    assert repairs.generate("none", "x = 1\n") == []


# --- guardrails --------------------------------------------------------------

def test_refuses_dangerous_target():
    with pytest.raises(GuardrailViolation, match="import os"):
        validate_inputs("game.py", "import os\n", "test_game.py", "from game import x\n")


def test_refuses_empty_and_unparseable_input():
    with pytest.raises(GuardrailViolation, match="empty"):
        validate_inputs("game.py", "   ", "test_game.py", "from game import x\n")
    with pytest.raises(GuardrailViolation, match="not valid Python"):
        validate_inputs("game.py", "def (:\n", "test_game.py", "from game import x\n")


def test_refuses_tests_that_do_not_import_target():
    with pytest.raises(GuardrailViolation, match="never imports"):
        validate_inputs("game.py", "x = 1\n", "test_game.py", "def test_a():\n    assert True\n")


def test_patch_guardrails():
    original = "def f():\n    return 1\n"
    assert validate_patch(original, original) == "patch makes no change"
    assert "banned" in validate_patch(original, "import subprocess\ndef f():\n    return 1\n")
    assert "deletes definitions" in validate_patch(original, "x = 1\n")
    assert validate_patch(original, "def f():\n    return 2\n") is None


# --- end-to-end agent (offline backend, real sandbox) -------------------------

def _run(case, **kw):
    spec = json.loads((CASES / case / "case.json").read_text(encoding="utf-8"))
    agent = GlitchAgent(backend=HeuristicBackend(), save_trace=False, **kw)
    return agent.investigate(CASES / case / "game.py", CASES / case / "test_game.py", spec["symptom"])


def test_agent_fixes_score_sign_bug():
    r = _run("03_score_sign")
    assert r.status == "fixed"
    assert r.patterns_used == ["score-sign-error"]
    assert "current_score - 5" in r.patched_source
    assert r.confidence >= 0.75


def test_agent_refuses_dangerous_case_without_running_it():
    r = _run("10_dangerous_input")
    assert r.status == "refused"
    assert not any(s["action"] == "observe" for s in r.trace)


def test_agent_hands_unfixable_case_to_human():
    r = _run("11_missing_feature")
    assert r.status == "needs_human_review"
    assert r.patched_source is None


def test_agent_never_edits_files_on_disk():
    before = (CASES / "01_inverted_hints" / "game.py").read_text(encoding="utf-8")
    _run("01_inverted_hints")
    assert (CASES / "01_inverted_hints" / "game.py").read_text(encoding="utf-8") == before


# --- Claude backend (fake client, no network) ----------------------------------

class FakeClient:
    """Stands in for anthropic.Anthropic(): records the request, returns canned JSON."""

    def __init__(self, payload, stop_reason="end_turn"):
        self.payload, self.stop_reason, self.calls = payload, stop_reason, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        block = SimpleNamespace(type="text", text=json.dumps(self.payload))
        return SimpleNamespace(content=[block], stop_reason=self.stop_reason)


def test_claude_backend_patch_is_verified_by_tests():
    pytest.importorskip("anthropic")
    fixed = (CASES / "03_score_sign" / "game.py").read_text(encoding="utf-8").replace(
        "return current_score + 5", "return current_score - 5")
    client = FakeClient({"diagnosis": "penalty uses + instead of -", "pattern_id": "score-sign-error",
                         "confidence": 0.9, "patched_source": fixed})
    r = GlitchAgent(backend=ClaudeBackend(client), save_trace=False).investigate(
        CASES / "03_score_sign" / "game.py", CASES / "03_score_sign" / "test_game.py", "score went up")
    assert r.status == "fixed"
    request = client.calls[0]
    assert request["model"] == "claude-opus-5-5"
    # RAG: the retrieved knowledge-base text is part of what Claude sees.
    assert "Score sign error on wrong guesses" in request["messages"][0]["content"]


def test_claude_backend_unsafe_patch_is_rejected_by_guardrail():
    pytest.importorskip("anthropic")
    client = FakeClient({"diagnosis": "x", "pattern_id": "unknown", "confidence": 0.99,
                         "patched_source": "import subprocess\n"})
    r = GlitchAgent(backend=ClaudeBackend(client), save_trace=False, max_iterations=1).investigate(
        CASES / "03_score_sign" / "game.py", CASES / "03_score_sign" / "test_game.py", "score went up")
    rejects = [s for s in r.trace if s["action"] == "reject"]
    assert rejects and "banned" in rejects[0]["reason"]
    assert r.status != "fixed"


def test_claude_failure_falls_back_to_offline_backend():
    pytest.importorskip("anthropic")
    client = FakeClient({}, stop_reason="max_tokens")
    r = GlitchAgent(backend=ClaudeBackend(client), save_trace=False).investigate(
        CASES / "03_score_sign" / "game.py", CASES / "03_score_sign" / "test_game.py", "score went up")
    assert any(s["action"] == "backend_error" for s in r.trace)
    assert "fallback" in r.backend
    assert r.status == "fixed"


def test_claude_refusal_raises_backend_error():
    pytest.importorskip("anthropic")
    backend = ClaudeBackend(FakeClient({}, stop_reason="refusal"))
    from glitch_agent.backends import Context
    with pytest.raises(BackendError):
        backend.propose(Context("game.py", "", "", {}, "", [], []))
