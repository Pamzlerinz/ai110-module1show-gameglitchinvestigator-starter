"""Glitch Investigator: a retrieval-augmented debugging agent for small Python games."""

from .agent import GlitchAgent, Result, make_backend, setup_logging

__all__ = ["GlitchAgent", "Result", "make_backend", "setup_logging"]
