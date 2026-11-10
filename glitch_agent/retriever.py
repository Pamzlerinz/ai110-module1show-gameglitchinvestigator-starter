"""Retrieval over the bug-pattern knowledge base (the "R" in RAG).

Two sources are indexed:

* ``knowledge_base/patterns/*.md``: one document per known bug pattern, with a
  front-matter ``repair:`` field naming the repair strategy that fixes it.
* ``knowledge_base/case_history.md``: real bugs from the original Module 1
  project, each linked to a pattern with a ``pattern:`` line.

Documents are split into chunks (one per ``##``/``###`` section) and ranked with
BM25. The agent turns the ranked chunks into an ordered list of *patterns*; that
list decides which repairs the offline backend tries and which reference
material the Claude backend sees, so retrieval directly shapes the fix.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "has",
    "if", "in", "into", "is", "it", "its", "of", "on", "or", "so", "such", "that",
    "the", "then", "this", "to", "was", "were", "when", "with", "test", "tests",
    "assert", "assertionerror", "py", "game", "def", "e", "where",
}


def tokenize(text: str) -> list[str]:
    """Lowercase, split on anything non-alphanumeric (so snake_case splits), and
    strip a trailing plural 's' so 'guesses' matches 'guess'."""
    tokens = []
    for raw in re.split(r"[^a-z0-9]+", text.lower()):
        if len(raw) > 3 and raw.endswith("s") and not raw.endswith("ss"):
            raw = raw[:-1]
        if len(raw) < 2 or raw in STOPWORDS:
            continue
        tokens.append(raw)
    return tokens


@dataclass
class Pattern:
    id: str
    title: str
    repair: str
    text: str


@dataclass
class Chunk:
    source: str          # "patterns" or "case_history"
    doc: str             # file name
    pattern_id: str      # pattern this chunk is evidence for
    heading: str
    text: str
    tokens: list[str] = field(default_factory=list, repr=False)


@dataclass
class Hit:
    chunk: Chunk
    score: float


def _front_matter(text: str) -> tuple[dict, str]:
    meta = {}
    if text.startswith("---"):
        _, header, body = text.split("---", 2)
        for line in header.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        return meta, body
    return meta, text


def _sections(body: str, level: str) -> list[tuple[str, str]]:
    parts = re.split(rf"^{level} +(.+)$", body, flags=re.MULTILINE)
    # parts = [preamble, heading1, text1, heading2, text2, ...]
    return [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts), 2)]


def load_patterns(kb_dir: Path = KB_DIR) -> dict[str, Pattern]:
    patterns = {}
    for path in sorted((kb_dir / "patterns").glob("*.md")):
        meta, body = _front_matter(path.read_text(encoding="utf-8"))
        patterns[meta["id"]] = Pattern(meta["id"], meta["title"], meta["repair"], body.strip())
    return patterns


def load_chunks(kb_dir: Path = KB_DIR, sources: tuple[str, ...] = ("patterns", "case_history")) -> list[Chunk]:
    chunks: list[Chunk] = []
    if "patterns" in sources:
        for path in sorted((kb_dir / "patterns").glob("*.md")):
            meta, body = _front_matter(path.read_text(encoding="utf-8"))
            for heading, text in _sections(body, "##"):
                chunks.append(Chunk("patterns", path.name, meta["id"], f"{meta['title']}: {heading}",
                                    f"{meta['title']}. {text}"))
    if "case_history" in sources:
        path = kb_dir / "case_history.md"
        _, body = _front_matter(path.read_text(encoding="utf-8"))
        for heading, text in _sections(body, "###"):
            m = re.search(r"^pattern:\s*(\S+)", text, flags=re.MULTILINE)
            if not m:
                continue
            chunks.append(Chunk("case_history", path.name, m.group(1), heading, f"{heading}. {text}"))
    for c in chunks:
        c.tokens = tokenize(c.text)
    return chunks


class Retriever:
    """BM25 ranking over knowledge-base chunks. Pure Python, no extra deps."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.avg_len = sum(len(c.tokens) for c in chunks) / max(len(chunks), 1)
        df = Counter()
        for c in chunks:
            df.update(set(c.tokens))
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    @classmethod
    def from_kb(cls, sources: tuple[str, ...] = ("patterns", "case_history")) -> "Retriever":
        return cls(load_chunks(sources=sources))

    def search(self, query: str, k: int = 6) -> list[Hit]:
        q = tokenize(query)
        hits = []
        for c in self.chunks:
            tf = Counter(c.tokens)
            score = 0.0
            for t in q:
                if t not in tf:
                    continue
                f = tf[t]
                denom = f + self.k1 * (1 - self.b + self.b * len(c.tokens) / self.avg_len)
                score += self.idf[t] * f * (self.k1 + 1) / denom
            if score > 0:
                hits.append(Hit(c, score))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]


def rank_patterns(hits: list[Hit]) -> list[tuple[str, float]]:
    """Collapse chunk hits into patterns ordered by their best chunk score,
    normalised so the top pattern has support 1.0."""
    best: dict[str, float] = {}
    for h in hits:
        best[h.chunk.pattern_id] = max(best.get(h.chunk.pattern_id, 0.0), h.score)
    if not best:
        return []
    top = max(best.values())
    return sorted(((pid, round(s / top, 3)) for pid, s in best.items()), key=lambda x: -x[1])
