"""Guardrails on what the agent accepts as input and what it may output.

Input checks run *before* any code executes. Patch checks run on every
candidate before it reaches the sandbox, so a bad proposal (from the offline
search or from Claude) is rejected with a logged reason instead of being run.
"""

from __future__ import annotations

import ast
import difflib

MAX_FILE_BYTES = 50_000
MAX_CHANGED_LINES = 20

BANNED_MODULES = {"os", "subprocess", "shutil", "socket", "ctypes", "requests",
                  "urllib", "http", "pathlib", "pickle", "multiprocessing"}
BANNED_CALLS = {"eval", "exec", "compile", "__import__", "open", "input", "breakpoint"}


class GuardrailViolation(Exception):
    """Raised when input is refused. The message is shown to the user."""


def _danger(tree: ast.AST) -> set[str]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {f"import {a.name}" for a in node.names if a.name.split(".")[0] in BANNED_MODULES}
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in BANNED_MODULES:
            found.add(f"from {node.module} import ...")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            found.add(f"call to {node.func.id}()")
    return found


def _parse(source: str, label: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as e:
        raise GuardrailViolation(f"{label} is not valid Python (line {e.lineno}: {e.msg})") from e


def validate_inputs(target_name: str, target_source: str, test_name: str, test_source: str) -> None:
    for label, src in (("target file", target_source), ("test file", test_source)):
        if not src.strip():
            raise GuardrailViolation(f"{label} is empty")
        if len(src.encode("utf-8")) > MAX_FILE_BYTES:
            raise GuardrailViolation(f"{label} is larger than {MAX_FILE_BYTES // 1000} KB")
    if not target_name.endswith(".py") or not test_name.endswith(".py"):
        raise GuardrailViolation("only .py files are supported")

    target_tree = _parse(target_source, "target file")
    test_tree = _parse(test_source, "test file")
    for label, tree in (("target file", target_tree), ("test file", test_tree)):
        danger = _danger(tree)
        if danger:
            raise GuardrailViolation(
                f"{label} uses operations the sandbox will not run: {', '.join(sorted(danger))}")

    module = target_name[:-3]
    imports_target = any(
        (isinstance(n, ast.ImportFrom) and n.module == module)
        or (isinstance(n, ast.Import) and any(a.name == module for a in n.names))
        for n in ast.walk(test_tree))
    if not imports_target:
        raise GuardrailViolation(f"test file never imports '{module}', so it cannot verify a fix")


def changed_lines(before: str, after: str) -> int:
    diff = difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
    return sum(1 for line in diff if line[:1] in "+-" and not line.startswith(("+++", "---")))


def validate_patch(original: str, patched: str) -> str | None:
    """Return None if the patch is acceptable, otherwise the rejection reason."""
    if patched == original:
        return "patch makes no change"
    try:
        new_tree = ast.parse(patched)
    except SyntaxError as e:
        return f"patch is not valid Python (line {e.lineno}: {e.msg})"
    added = _danger(new_tree) - _danger(ast.parse(original))
    if added:
        return f"patch adds banned operations: {', '.join(sorted(added))}"
    defs = lambda t: {n.name for n in ast.walk(t) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    removed = defs(ast.parse(original)) - defs(new_tree)
    if removed:
        return f"patch deletes definitions: {', '.join(sorted(removed))}"
    n = changed_lines(original, patched)
    if n > MAX_CHANGED_LINES:
        return f"patch changes {n} lines (limit {MAX_CHANGED_LINES})"
    return None
