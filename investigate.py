"""Command-line entry point for the Glitch Investigator agent.

    python investigate.py <target.py> --tests <test_file.py> [--symptom "..."]

By default the agent only *proposes* a fix (a diff). Pass --apply to write it
back to the target file; a .bak copy of the original is kept.
"""

import argparse
import shutil
import sys
from pathlib import Path

from glitch_agent import GlitchAgent, make_backend, setup_logging

ICONS = {"fixed": "✅", "partial": "🟡", "needs_human_review": "🧑‍🔧",
         "no_bug_detected": "🟢", "refused": "⛔"}


def format_step(s: dict) -> str:
    """One readable line per trace step (the JSON trace file has every field)."""
    a = s["action"]
    if a == "plan":
        return f"backend={s['backend']} retrieval={s['retrieval']} plan: " + " -> ".join(s["plan"])
    if a == "observe":
        failing = ", ".join(s["failing"]) or "none"
        return f"tests {s['tests']}; failing: {failing}" + (f"; errors: {s['errors']}" if s["errors"] else "")
    if a == "retrieve":
        if "hits" not in s:
            return s["mode"]
        hits = "; ".join(f"{h['source']}:{h['pattern']} ({h['score']})" for h in s["hits"][:4])
        return f"top chunks: {hits} => patterns: {', '.join(s['patterns'])}"
    if a == "propose":
        return f"iteration {s['iteration']}: {s['count']} candidate patch(es)"
    if a == "verify":
        return f"[{s['pattern']}] {s['candidate']} => {s['result']}"
    if a == "reject":
        return f"{s['candidate']} => rejected: {s['reason']}"
    if a == "accept":
        return f"iteration {s['iteration']}: keep [{s['pattern']}] {s['change']} ({s['tests']})"
    extra = {k: v for k, v in s.items() if k not in ("step", "action")}
    return ", ".join(f"{k}={v}" for k, v in extra.items())


def print_report(result, show_trace: bool) -> None:
    print(f"\n{ICONS.get(result.status, '')} STATUS: {result.status}   confidence={result.confidence}")
    print(f"   {result.message}")
    print(f"   backend: {result.backend}")
    if result.tests_before:
        print(f"   tests: {result.tests_before} -> {result.tests_after or result.tests_before}"
              f"   (iterations={result.iterations}, candidates tested={result.candidates_tried})")
    if result.retrieved:
        print("   retrieved patterns: " + ", ".join(f"{r['pattern']} ({r['support']})" for r in result.retrieved[:5]))
    for d in result.diagnosis:
        print(f"   diagnosis: {d}")
    if result.still_failing:
        print("   still failing: " + ", ".join(result.still_failing))
    if result.diff:
        print("\n--- proposed patch " + "-" * 50)
        print(result.diff.rstrip())
    if show_trace:
        print("\n--- agent trace " + "-" * 53)
        for s in result.trace:
            print(f"  {s['step']:>2}. {s['action']:<8} {format_step(s)}")
    if result.trace_file:
        print(f"\n   full trace saved to {Path(result.trace_file).relative_to(Path.cwd()) if Path(result.trace_file).is_relative_to(Path.cwd()) else result.trace_file}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Diagnose and fix a buggy Python module using its tests.")
    ap.add_argument("target", help="Python module to investigate")
    ap.add_argument("--tests", required=True, help="pytest file that imports the target")
    ap.add_argument("--symptom", default="", help="what the player/user observed, in plain words")
    ap.add_argument("--backend", choices=["auto", "offline", "claude"], default="auto",
                    help="auto = Claude if ANTHROPIC_API_KEY is set, otherwise offline")
    ap.add_argument("--no-retrieval", action="store_true", help="ablation: skip the knowledge base")
    ap.add_argument("--apply", action="store_true", help="write the verified fix to the target file")
    ap.add_argument("--trace", action="store_true", help="print every agent step")
    ap.add_argument("--verbose", action="store_true", help="echo log lines to the console")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    setup_logging(console=args.verbose)
    agent = GlitchAgent(backend=make_backend(args.backend), use_retrieval=not args.no_retrieval)
    result = agent.investigate(args.target, args.tests, args.symptom)
    print_report(result, args.trace)

    if args.apply:
        if result.status != "fixed" or not result.patched_source:
            print("\n--apply skipped: only verified fixes above the confidence threshold are written.")
            return 1
        target = Path(args.target)
        shutil.copyfile(target, target.with_suffix(target.suffix + ".bak"))
        target.write_text(result.patched_source, encoding="utf-8")
        print(f"\nApplied. Original saved as {target.name}.bak")
    return 0 if result.status in ("fixed", "no_bug_detected") else 1


if __name__ == "__main__":
    sys.exit(main())
