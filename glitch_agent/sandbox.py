"""Run a target module against its pytest suite in a throwaway directory.

The agent never edits the user's files while it experiments. Every candidate
patch is written to a fresh temp directory next to an unmodified copy of the
tests, and pytest runs there in a subprocess with a timeout.

This is isolation from the user's files, not a security sandbox; the static
checks in ``guardrails.py`` run first and refuse obviously dangerous code.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

TIMEOUT_SECONDS = 30

_RESULT_LINE = re.compile(r"^(PASSED|FAILED|ERROR) (\S+?)(?: - (.*))?$")


@dataclass
class TestRun:
    passed: set[str] = field(default_factory=set)
    failed: dict[str, str] = field(default_factory=dict)  # test id -> short message
    errors: list[str] = field(default_factory=list)       # collection errors / timeouts
    output: str = ""

    @property
    def total(self) -> int:
        return len(self.passed) + len(self.failed)

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and not self.failed and not self.errors

    def summary(self) -> str:
        if self.errors:
            return f"ERROR ({'; '.join(self.errors)[:120]})"
        return f"{len(self.passed)}/{self.total} passed"


def run_tests(target_name: str, target_source: str, test_name: str, test_source: str) -> TestRun:
    with tempfile.TemporaryDirectory(prefix="glitch_sandbox_") as tmp:
        Path(tmp, target_name).write_text(target_source, encoding="utf-8")
        Path(tmp, test_name).write_text(test_source, encoding="utf-8")
        cmd = [sys.executable, "-m", "pytest", test_name, "-q", "-rA", "--tb=line",
               "-p", "no:cacheprovider", "-o", "addopts=", f"--rootdir={tmp}"]
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            proc = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=TIMEOUT_SECONDS, env=env)
        except subprocess.TimeoutExpired:
            return TestRun(errors=[f"timed out after {TIMEOUT_SECONDS}s"])

    run = TestRun(output=proc.stdout + proc.stderr)
    for line in proc.stdout.splitlines():
        m = _RESULT_LINE.match(line.strip())
        if not m:
            continue
        kind, test_id, msg = m.groups()
        test_id = test_id.split("::", 1)[-1]
        if kind == "PASSED":
            run.passed.add(test_id)
        elif kind == "FAILED":
            run.failed[test_id] = (msg or "").strip()
        else:
            run.errors.append(f"{test_id}: {(msg or '').strip()}")
    if run.total == 0 and not run.errors:
        run.errors.append("no tests were collected (pytest exit code %d)" % proc.returncode)
    return run
