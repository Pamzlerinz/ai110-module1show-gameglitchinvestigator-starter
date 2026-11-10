"""Backends that turn (failing tests + retrieved knowledge) into proposed patches.

* ``ClaudeBackend``: sends the code, the failing tests, the retrieved pattern
  docs and any earlier failed attempts to Claude and asks for a diagnosis and a
  patched file as structured JSON.
* ``HeuristicBackend``: fully offline and deterministic. It reads the
  ``repair:`` field of each *retrieved* pattern and generates candidates with
  that pattern's repair strategy. It never invents a fix that retrieval did not
  point it to, so what it can fix depends on what retrieval returns.

Both return the same ``Proposal`` objects, and the agent verifies them the same way.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from . import repairs
from .repairs import Candidate
from .retriever import Hit, Pattern

log = logging.getLogger("glitch_agent")

CLAUDE_MODEL = "claude-opus-5-5"


@dataclass
class Context:
    target_name: str
    original_source: str
    current_source: str
    failing: dict[str, str]
    symptom: str
    patterns: list[tuple[Pattern, float]]     # ranked, with normalised support
    hits: list[Hit]
    attempts: list[dict] = field(default_factory=list)


@dataclass
class Proposal:
    candidate: Candidate
    pattern_id: str
    diagnosis: str
    model_confidence: float | None = None


class BackendError(Exception):
    pass


def _first_sentence(text: str) -> str:
    body = text.split("## Root cause", 1)[-1].split("##", 1)[0].strip()
    return body.split(". ")[0].rstrip(".") + "."


class HeuristicBackend:
    name = "offline-heuristic"

    def __init__(self, max_candidates: int = 40):
        self.max_candidates = max_candidates

    def propose(self, ctx: Context) -> list[Proposal]:
        proposals: list[Proposal] = []
        for pattern, _support in ctx.patterns:
            for cand in repairs.generate(pattern.repair, ctx.current_source):
                proposals.append(Proposal(cand, pattern.id,
                                          f"{pattern.title}: {_first_sentence(pattern.text)}"))
        return proposals[: self.max_candidates]


SYSTEM_PROMPT = """You are Glitch Investigator, a debugging agent for small Python game modules.
You receive a buggy module, the pytest failures it produces, and reference notes retrieved
from a bug-pattern knowledge base (including the team's own past bug reports).

Rules:
- Make the smallest change that makes the failing tests pass without breaking passing ones.
- Never change test expectations; you only edit the target module.
- Keep every existing function and class name. Do not add imports.
- Prefer the fix recipe from a retrieved pattern when one matches. Set pattern_id to that
  pattern's id, or "unknown" if none of them explains the failure.
- confidence is your probability (0 to 1) that the patch is correct. Be calibrated: if the tests
  ask for behaviour the module does not implement at all, say so in the diagnosis and give a
  low confidence instead of guessing.
- patched_source is the complete new file content, with no markdown fences."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis": {"type": "string"},
        "pattern_id": {"type": "string"},
        "confidence": {"type": "number"},
        "patched_source": {"type": "string"},
    },
    "required": ["diagnosis", "pattern_id", "confidence", "patched_source"],
    "additionalProperties": False,
}


class ClaudeBackend:
    name = f"claude ({CLAUDE_MODEL})"

    def __init__(self, client=None):
        if client is None:
            import anthropic  # imported lazily so offline mode needs no SDK
            client = anthropic.Anthropic()
        self.client = client

    @staticmethod
    def available() -> bool:
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def build_prompt(self, ctx: Context) -> str:
        refs = "\n\n".join(f"[{h.chunk.source} / {h.chunk.pattern_id}] {h.chunk.heading}\n{h.chunk.text}"
                           for h in ctx.hits) or "(no matching references)"
        failing = "\n".join(f"- {t}: {m}" for t, m in ctx.failing.items())
        tries = "\n".join(f"- attempt {a['iteration']}: {a['description']} -> {a['result']}"
                          for a in ctx.attempts) or "(none yet)"
        return (f"Symptom reported by the user: {ctx.symptom or '(none given)'}\n\n"
                f"Failing tests:\n{failing}\n\n"
                f"Retrieved references:\n{refs}\n\n"
                f"Earlier attempts this session:\n{tries}\n\n"
                f"Module `{ctx.target_name}`:\n```python\n{ctx.current_source}\n```")

    def propose(self, ctx: Context) -> list[Proposal]:
        import anthropic

        try:
            response = self.client.beta.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                output_config={"effort": "medium",
                               "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": self.build_prompt(ctx)}],
            )
        except anthropic.AuthenticationError as e:
            raise BackendError("Claude rejected the API key") from e
        except anthropic.RateLimitError as e:
            raise BackendError("Claude rate limit reached") from e
        except anthropic.APIStatusError as e:
            raise BackendError(f"Claude API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise BackendError("could not reach the Claude API") from e

        if response.stop_reason == "refusal":
            raise BackendError("Claude declined the request")
        if response.stop_reason == "max_tokens":
            raise BackendError("Claude's answer was cut off (max_tokens)")
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = json.loads(text)
            patched = data["patched_source"]
            confidence = max(0.0, min(1.0, float(data["confidence"])))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            raise BackendError(f"Claude returned malformed JSON: {e}") from e
        if patched.lstrip().startswith("```"):
            patched = patched.strip().strip("`").removeprefix("python").strip() + "\n"
        log.info("claude proposal pattern=%s confidence=%.2f request_id=%s",
                 data["pattern_id"], confidence, getattr(response, "_request_id", None))
        cand = Candidate("claude_patch", data["diagnosis"][:160], patched, 0)
        return [Proposal(cand, data["pattern_id"], data["diagnosis"], confidence)]
