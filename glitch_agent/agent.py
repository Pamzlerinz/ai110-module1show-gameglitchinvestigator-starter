"""The Glitch Investigator agent loop.

    validate input -> run tests (observe) -> retrieve patterns -> propose patches
        -> guardrail check -> run tests on each candidate (verify)
        -> keep the best non-regressing patch -> repeat on what still fails
        -> score confidence -> report (a human decides whether to apply it)

Every step is appended to a trace that is logged and saved as JSON, so a run can
be audited after the fact.
"""

from __future__ import annotations

import datetime as dt
import difflib
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import guardrails, sandbox
from .backends import BackendError, ClaudeBackend, Context, HeuristicBackend, Proposal
from .guardrails import GuardrailViolation
from .retriever import Retriever, load_patterns, rank_patterns

log = logging.getLogger("glitch_agent")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
CONFIDENCE_THRESHOLD = 0.75


@dataclass
class Result:
    status: str                      # fixed | partial | needs_human_review | no_bug_detected | refused
    message: str
    backend: str
    confidence: float = 0.0
    diagnosis: list[str] = field(default_factory=list)
    patterns_used: list[str] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    tests_before: str = ""
    tests_after: str = ""
    still_failing: list[str] = field(default_factory=list)
    iterations: int = 0
    candidates_tried: int = 0
    patched_source: str | None = None
    diff: str = ""
    trace: list[dict] = field(default_factory=list)
    trace_file: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


def make_backend(choice: str = "auto"):
    if choice == "claude":
        # Fail early with a clear message instead of a TypeError from deep
        # inside the SDK on the first API call.
        if not ClaudeBackend.available():
            raise RuntimeError(
                "the Claude backend needs ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN) "
                "set and the anthropic package installed. Set the key, or use the "
                "offline backend instead."
            )
        return ClaudeBackend()
    if choice == "auto" and ClaudeBackend.available():
        return ClaudeBackend()
    return HeuristicBackend()


class GlitchAgent:
    def __init__(self, backend=None, use_retrieval: bool = True,
                 sources: tuple[str, ...] = ("patterns", "case_history"),
                 max_iterations: int = 4, candidate_budget: int = 40, top_k: int = 6,
                 save_trace: bool = True):
        self.backend = backend or make_backend()
        self.use_retrieval = use_retrieval
        self.retriever = Retriever.from_kb(sources)
        self.patterns = load_patterns()
        self.max_iterations = max_iterations
        self.candidate_budget = candidate_budget
        self.top_k = top_k
        self.save_trace = save_trace

    # -- helpers -------------------------------------------------------------

    def _step(self, trace: list, action: str, **detail) -> None:
        entry = {"step": len(trace) + 1, "action": action, **detail}
        trace.append(entry)
        log.info("step %d %s %s", entry["step"], action,
                 json.dumps(detail, ensure_ascii=False, default=str)[:300])

    def _retrieve(self, symptom: str, failing: dict[str, str], trace: list):
        if not self.use_retrieval:
            # Ablation mode: no knowledge base, so try every repair blindly.
            ranked = [(p, 0.0) for p in self.patterns.values() if p.repair != "none"]
            self._step(trace, "retrieve", mode="disabled (blind search over all strategies)",
                       patterns=[p.id for p, _ in ranked])
            return ranked, []
        query = " ".join([symptom, *failing.keys(), *failing.values()])
        hits = self.retriever.search(query, k=self.top_k)
        ranked = [(self.patterns[pid], s) for pid, s in rank_patterns(hits) if pid in self.patterns]
        self._step(trace, "retrieve", query=query[:200],
                   hits=[{"source": h.chunk.source, "pattern": h.chunk.pattern_id,
                          "heading": h.chunk.heading, "score": round(h.score, 2)} for h in hits],
                   patterns=[f"{p.id} ({s})" for p, s in ranked])
        return ranked, hits

    @staticmethod
    def _confidence(run: sandbox.TestRun, support: float, changed: int, model_conf: float | None) -> float:
        pass_ratio = len(run.passed) / run.total if run.total else 0.0
        minimality = 1.0 if changed <= 8 else 0.5 if changed <= 20 else 0.0  # counts +/- lines
        score = 0.55 * pass_ratio + 0.30 * support + 0.15 * minimality
        if model_conf is not None:
            score = 0.7 * score + 0.3 * model_conf
        return round(score, 2)

    # -- main loop -----------------------------------------------------------

    def investigate(self, target_path: str | Path, test_path: str | Path, symptom: str = "") -> Result:
        target_path, test_path = Path(target_path), Path(test_path)
        trace: list[dict] = []
        backend_name = self.backend.name
        self._step(trace, "plan", target=str(target_path), tests=str(test_path), symptom=symptom,
                   backend=backend_name, retrieval=self.use_retrieval,
                   plan=["validate input", "run tests", "retrieve bug patterns", "propose patches",
                         "guardrail-check + verify each patch", "iterate on remaining failures",
                         "score confidence and report for human approval"])

        try:
            target_src = target_path.read_text(encoding="utf-8")
            test_src = test_path.read_text(encoding="utf-8")
            guardrails.validate_inputs(target_path.name, target_src, test_path.name, test_src)
        except (OSError, UnicodeDecodeError, GuardrailViolation) as e:
            self._step(trace, "refuse", reason=str(e))
            return self._finish(Result("refused", f"Refused: {e}", backend_name, trace=trace), target_path)
        self._step(trace, "validate", ok=True)

        run = sandbox.run_tests(target_path.name, target_src, test_path.name, test_src)
        self._step(trace, "observe", tests=run.summary(), failing=run.failed, errors=run.errors)
        result = Result("needs_human_review", "", backend_name, tests_before=run.summary(), trace=trace)
        if run.errors:
            result.message = "The test suite could not run cleanly, so no fix can be verified: " + "; ".join(run.errors)
            return self._finish(result, target_path)
        if run.all_passed:
            result.status, result.confidence = "no_bug_detected", 1.0
            result.message = "All tests already pass. No change proposed."
            result.tests_after = run.summary()
            return self._finish(result, target_path)

        current_src, current_run = target_src, run
        attempts: list[dict] = []
        accepted: list[Proposal] = []
        supports: list[float] = []
        best_support = 0.0
        for iteration in range(1, self.max_iterations + 1):
            result.iterations = iteration
            ranked, hits = self._retrieve(symptom, current_run.failed, trace)
            support_of = {p.id: s for p, s in ranked}
            result.retrieved = [{"pattern": p.id, "support": s} for p, s in ranked]
            ctx = Context(target_path.name, target_src, current_src, current_run.failed, symptom,
                          ranked, hits, attempts)
            try:
                proposals = self.backend.propose(ctx)
            except BackendError as e:
                self._step(trace, "backend_error", error=str(e), fallback="offline-heuristic")
                self.backend = HeuristicBackend()
                result.backend = backend_name = f"{backend_name} -> offline-heuristic (fallback)"
                proposals = self.backend.propose(ctx)
            self._step(trace, "propose", iteration=iteration, count=len(proposals),
                       candidates=[f"[{p.pattern_id}] {p.candidate.description}" for p in proposals[:12]])

            best: tuple[Proposal, sandbox.TestRun] | None = None
            for prop in proposals:
                if result.candidates_tried >= self.candidate_budget:
                    self._step(trace, "budget_exhausted", budget=self.candidate_budget)
                    break
                reason = guardrails.validate_patch(target_src, prop.candidate.source)
                if reason:
                    self._step(trace, "reject", candidate=prop.candidate.description, reason=reason)
                    attempts.append({"iteration": iteration, "description": prop.candidate.description,
                                     "result": f"rejected by guardrail: {reason}"})
                    continue
                result.candidates_tried += 1
                trial = sandbox.run_tests(target_path.name, prop.candidate.source, test_path.name, test_src)
                regressed = sorted(current_run.passed - trial.passed)
                verdict = ("regression: " + ", ".join(regressed)) if regressed else trial.summary()
                self._step(trace, "verify", candidate=prop.candidate.description,
                           pattern=prop.pattern_id, result=verdict)
                attempts.append({"iteration": iteration, "description": prop.candidate.description,
                                 "result": verdict})
                if regressed or trial.errors:
                    continue
                if len(trial.passed) > len((best[1] if best else current_run).passed):
                    best = (prop, trial)
                    if trial.all_passed:
                        break
            if best is None:
                self._step(trace, "stuck", reason="no candidate improved the test results without regressions")
                break
            prop, trial = best
            accepted.append(prop)
            supports.append(support_of.get(prop.pattern_id, 0.0))
            current_src, current_run = prop.candidate.source, trial
            self._step(trace, "accept", iteration=iteration, pattern=prop.pattern_id,
                       change=prop.candidate.description, tests=trial.summary())
            if trial.all_passed:
                break

        result.tests_after = current_run.summary()
        result.still_failing = sorted(current_run.failed)
        result.diagnosis = [p.diagnosis for p in accepted]
        result.patterns_used = [p.pattern_id for p in accepted]
        if not accepted:
            result.message = ("No verified fix. The failing tests do not match any repair the agent "
                              "could confirm; a human should investigate.")
            result.confidence = 0.0  # confidence is "confidence in a proposed fix"; there is none
            return self._finish(result, target_path)

        result.patched_source = current_src
        result.diff = "".join(difflib.unified_diff(
            target_src.splitlines(keepends=True), current_src.splitlines(keepends=True),
            fromfile=f"a/{target_path.name}", tofile=f"b/{target_path.name}"))
        model_confs = [p.model_confidence for p in accepted if p.model_confidence is not None]
        result.confidence = self._confidence(
            current_run, min(supports) if supports else 0.0,
            guardrails.changed_lines(target_src, current_src),
            min(model_confs) if model_confs else None)
        if current_run.all_passed and result.confidence >= CONFIDENCE_THRESHOLD:
            result.status = "fixed"
            result.message = f"All tests pass after {len(accepted)} verified change(s)."
        elif current_run.all_passed:
            result.status = "needs_human_review"
            result.message = (f"Tests pass, but confidence {result.confidence} is below "
                              f"{CONFIDENCE_THRESHOLD}; review the diff carefully.")
        else:
            result.status = "partial"
            result.message = f"Improved {run.summary()} -> {current_run.summary()}; some tests still fail."
        return self._finish(result, target_path)

    def _finish(self, result: Result, target_path: Path) -> Result:
        self._step(result.trace, "report", status=result.status, confidence=result.confidence,
                   message=result.message)
        if self.save_trace:
            (LOG_DIR / "traces").mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            path = LOG_DIR / "traces" / f"{stamp}_{target_path.parent.name}_{target_path.stem}.json"
            path.write_text(result.to_json(), encoding="utf-8")
            result.trace_file = str(path)
        return result


def setup_logging(level: int = logging.INFO, console: bool = False) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger("glitch_agent")
    if logger.handlers:
        return
    logger.setLevel(level)
    fh = logging.FileHandler(LOG_DIR / "glitch_agent.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)
    if console:
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("  [log] %(message)s"))
        logger.addHandler(sh)
