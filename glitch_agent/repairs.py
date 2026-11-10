"""Repair strategies: small, targeted edits that generate candidate patches.

Every knowledge-base pattern names one strategy in its ``repair:`` field. A
strategy takes source text and yields ``Candidate`` patches, one per place it
could apply. Candidates are hypotheses only: the agent keeps one only if the
guardrails accept it and the target's own tests confirm it.

Edits are spliced into the original text by AST position (rather than
re-generating the file with ``ast.unparse``) so comments and formatting survive
and diffs stay minimal.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass
from typing import Callable, Iterator


@dataclass
class Candidate:
    strategy: str
    description: str
    source: str
    line: int


class _Source:
    """Maps AST (line, byte-column) positions to character offsets in text."""

    def __init__(self, text: str):
        self.text = text
        self.lines = text.splitlines(keepends=True)
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line))

    def offset(self, lineno: int, col_bytes: int) -> int:
        line = self.lines[lineno - 1]
        return self.starts[lineno - 1] + len(line.encode("utf-8")[:col_bytes].decode("utf-8", "ignore"))

    def span(self, node: ast.AST) -> tuple[int, int]:
        return (self.offset(node.lineno, node.col_offset),
                self.offset(node.end_lineno, node.end_col_offset))

    def seg(self, node: ast.AST) -> str:
        a, b = self.span(node)
        return self.text[a:b]

    def replace(self, node: ast.AST, new: str) -> str:
        a, b = self.span(node)
        return self.text[:a] + new + self.text[b:]

    def insert_line(self, lineno: int, new_line: str) -> str:
        """Insert ``new_line`` (without newline) before 1-based line ``lineno``."""
        pos = self.starts[lineno - 1]
        return self.text[:pos] + new_line + "\n" + self.text[pos:]


_ATOMIC = (ast.Name, ast.Constant, ast.Call, ast.Attribute, ast.Subscript)


def _operand(src: _Source, node: ast.AST) -> str:
    text = src.seg(node)
    return text if isinstance(node, _ATOMIC) else f"({text})"


def _is_int(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is int


def _parses(text: str) -> bool:
    try:
        ast.parse(text)
        return True
    except SyntaxError:
        return False


# --- strategies -------------------------------------------------------------

_DIRECTION_SWAP = {"HIGHER": "LOWER", "LOWER": "HIGHER", "Higher": "Lower", "Lower": "Higher",
                   "higher": "lower", "lower": "higher", "📈": "📉", "📉": "📈"}
_DIRECTION_RE = re.compile("|".join(map(re.escape, _DIRECTION_SWAP)))


def swap_direction_words(text: str) -> Iterator[Candidate]:
    """Swap higher/lower (and up/down arrows) inside string literals only."""
    string_types = {tokenize.STRING} | {getattr(tokenize, "FSTRING_MIDDLE", -1)}
    src = _Source(text)
    edits = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in string_types and _DIRECTION_RE.search(tok.string):
            # tokenize columns are character offsets, unlike ast's byte offsets
            a = src.starts[tok.start[0] - 1] + tok.start[1]
            b = src.starts[tok.end[0] - 1] + tok.end[1]
            edits.append((a, b, _DIRECTION_RE.sub(lambda m: _DIRECTION_SWAP[m.group()], tok.string)))
    if not edits:
        return
    new = text
    for a, b, rep in sorted(edits, reverse=True):
        new = new[:a] + rep + new[b:]
    first = min(text.count("\n", 0, a) + 1 for a, _, _ in edits)
    yield Candidate("swap_direction_words", f"swap HIGHER/LOWER wording in {len(edits)} string literal(s)", new, first)


def remove_str_cast(text: str) -> Iterator[Candidate]:
    """Drop one ``str(x)`` conversion so a value keeps its numeric type."""
    src = _Source(text)
    tree = ast.parse(text)
    # `x = str(x)` alone inside an `if` would become the no-op `x = x`; in that
    # case drop the whole `if` block instead of leaving dead code behind.
    whole_if = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.If) and not node.orelse and len(node.body) == 1
                and isinstance(node.body[0], ast.Assign) and len(node.body[0].targets) == 1):
            whole_if[id(node.body[0].value)] = (node, node.body[0])
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str"
                and len(node.args) == 1 and not node.keywords):
            inner = src.seg(node.args[0])
            if id(node) in whole_if and src.seg(whole_if[id(node)][1].targets[0]) == inner:
                block, _ = whole_if[id(node)]
                start = src.starts[block.lineno - 1]
                end = src.starts[block.end_lineno]
                yield Candidate("remove_str_cast",
                                f"remove `{inner} = str({inner})` (and its `if {src.seg(block.test)}` guard)",
                                text[:start] + text[end:], node.lineno)
            else:
                yield Candidate("remove_str_cast", f"replace str({inner}) with {inner}",
                                src.replace(node, inner), node.lineno)


def flip_arith_sign(text: str) -> Iterator[Candidate]:
    """Flip + and - where one operand is an integer constant (score penalties)."""
    src = _Source(text)
    flip = {ast.Add: ("-", "-="), ast.Sub: ("+", "+=")}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.BinOp) and type(node.op) in flip and (_is_int(node.left) or _is_int(node.right)):
            new_op = flip[type(node.op)][0]
            rep = f"{_operand(src, node.left)} {new_op} {_operand(src, node.right)}"
            yield Candidate("flip_arith_sign", f"change `{src.seg(node)}` to `{rep}`", src.replace(node, rep), node.lineno)
        elif isinstance(node, ast.AugAssign) and type(node.op) in flip and _is_int(node.value):
            rep = f"{src.seg(node.target)} {flip[type(node.op)][1]} {src.seg(node.value)}"
            yield Candidate("flip_arith_sign", f"change `{src.seg(node)}` to `{rep}`", src.replace(node, rep), node.lineno)


_OP_TEXT = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=",
            ast.Is: "is", ast.IsNot: "is not", ast.In: "in", ast.NotIn: "not in"}


def _compare_flips(text: str, mapping: dict, strategy: str) -> Iterator[Candidate]:
    src = _Source(text)
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, ast.Compare):
            continue
        for i, op in enumerate(node.ops):
            if type(op) not in mapping:
                continue
            ops = [_OP_TEXT[type(o)] for o in node.ops]
            old_op, ops[i] = ops[i], mapping[type(op)]
            parts = [_operand(src, node.left)]
            for o, comp in zip(ops, node.comparators):
                parts += [o, _operand(src, comp)]
            rep = " ".join(parts)
            yield Candidate(strategy, f"change `{old_op}` to `{ops[i]}` in `{src.seg(node)}`",
                            src.replace(node, rep), node.lineno)


def fix_comparison_boundary(text: str) -> Iterator[Candidate]:
    """Make one comparison inclusive/exclusive (< <-> <=, > <-> >=)."""
    yield from _compare_flips(text, {ast.Lt: "<=", ast.LtE: "<", ast.Gt: ">=", ast.GtE: ">"},
                              "fix_comparison_boundary")


def flip_comparison_direction(text: str) -> Iterator[Candidate]:
    """Reverse one comparison (< <-> >, <= <-> >=)."""
    yield from _compare_flips(text, {ast.Lt: ">", ast.Gt: "<", ast.LtE: ">=", ast.GtE: "<="},
                              "flip_comparison_direction")


def adjust_int_constant(text: str) -> Iterator[Candidate]:
    """Nudge one integer constant by +/-1, or drop a stray ``+ 1`` / ``- 1``."""
    src = _Source(text)
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if _is_int(node):
            for delta in (-1, 1):
                value = node.value + delta
                if node.value >= 0 and value < 0:
                    continue
                yield Candidate("adjust_int_constant", f"change constant {node.value} to {value}",
                                src.replace(node, str(value)), node.lineno)
        elif (isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub))
              and _is_int(node.right) and node.right.value == 1):
            yield Candidate("adjust_int_constant", f"remove stray `{src.seg(node)[len(src.seg(node.left)):].strip()}`",
                            src.replace(node, src.seg(node.left)), node.lineno)


def complete_state_reset(text: str) -> Iterator[Candidate]:
    """Add the keys a reset function forgets, using the initial-state dict as truth."""
    tree = ast.parse(text)
    src = _Source(text)
    defaults: dict[str, str] = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        params = {a.arg for a in fn.args.args}
        for ret in ast.walk(fn):
            if isinstance(ret, ast.Return) and isinstance(ret.value, ast.Dict):
                for k, v in zip(ret.value.keys, ret.value.values):
                    names = {n.id for n in ast.walk(v) if isinstance(n, ast.Name)}
                    if isinstance(k, ast.Constant) and isinstance(k.value, str) and not names & params:
                        defaults.setdefault(k.value, src.seg(v))
    if not defaults:
        return
    for fn in ast.walk(tree):
        if not (isinstance(fn, ast.FunctionDef) and re.search(r"reset|new_game|restart", fn.name)):
            continue
        assigns = [s for s in fn.body if isinstance(s, ast.Assign) and len(s.targets) == 1
                   and isinstance(s.targets[0], ast.Subscript)
                   and isinstance(s.targets[0].value, ast.Name)
                   and isinstance(s.targets[0].slice, ast.Constant)]
        if not assigns:
            continue
        var = assigns[0].targets[0].value.id
        present = {s.targets[0].slice.value for s in assigns}
        missing = [k for k in defaults if k not in present]
        if not missing:
            continue
        last = assigns[-1]
        indent = " " * last.col_offset
        new = text
        for key in reversed(missing):
            new = _Source(new).insert_line(last.end_lineno + 1, f'{indent}{var}["{key}"] = {defaults[key]}')
        yield Candidate("complete_state_reset", f"{fn.name}() also resets {', '.join(missing)}", new, last.lineno)


def fix_mutable_default(text: str) -> Iterator[Candidate]:
    """Replace a list/dict/set default argument with None plus a fresh object."""
    src = _Source(text)
    for fn in ast.walk(ast.parse(text)):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        positional = fn.args.posonlyargs + fn.args.args
        pairs = list(zip(positional[len(positional) - len(fn.args.defaults):], fn.args.defaults))
        pairs += [(a, d) for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults) if d is not None]
        for arg, default in pairs:
            if not isinstance(default, (ast.List, ast.Dict, ast.Set)):
                continue
            body = fn.body
            first = body[1] if (len(body) > 1 and isinstance(body[0], ast.Expr)
                                and isinstance(body[0].value, ast.Constant)
                                and isinstance(body[0].value.value, str)) else body[0]
            indent = " " * first.col_offset
            fresh = src.seg(default)
            # Insert the body lines first (they come later in the file), then
            # swap the default, so earlier offsets stay valid.
            new = _Source(text).insert_line(first.lineno, f"{indent}if {arg.arg} is None:\n{indent}    {arg.arg} = {fresh}")
            new = _Source(new).replace(default, "None")
            yield Candidate("fix_mutable_default", f"{fn.name}(): default {arg.arg}={fresh} -> None",
                            new, fn.lineno)


STRATEGIES: dict[str, Callable[[str], Iterator[Candidate]]] = {
    "swap_direction_words": swap_direction_words,
    "remove_str_cast": remove_str_cast,
    "flip_arith_sign": flip_arith_sign,
    "fix_comparison_boundary": fix_comparison_boundary,
    "flip_comparison_direction": flip_comparison_direction,
    "adjust_int_constant": adjust_int_constant,
    "complete_state_reset": complete_state_reset,
    "fix_mutable_default": fix_mutable_default,
}


def generate(strategy: str, text: str) -> list[Candidate]:
    fn = STRATEGIES.get(strategy)
    if fn is None:
        return []
    return [c for c in fn(text) if _parses(c.source)]
