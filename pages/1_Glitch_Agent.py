"""Streamlit page: run the Glitch Investigator agent from the browser.

Pick a sample case (or paste your own module and tests), describe the symptom,
and the agent diagnoses, patches and verifies. Nothing is written to disk; the
human reviews the diff and decides whether to download the fix.
"""

import json
import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from glitch_agent import GlitchAgent, make_backend, setup_logging  # noqa: E402

CASES = Path(__file__).resolve().parent.parent / "eval" / "cases"

st.set_page_config(page_title="Glitch Agent", page_icon="🕵️")
st.title("🕵️ Glitch Investigator Agent")
st.caption("Retrieves known bug patterns, proposes a patch, runs your tests, and only "
           "reports a fix it has verified.")
setup_logging()

with st.sidebar:
    backend_choice = st.radio("Reasoning backend", ["auto", "offline", "claude"],
                              help="auto uses Claude when ANTHROPIC_API_KEY is set, otherwise the offline planner.")
    use_retrieval = st.checkbox("Use knowledge-base retrieval (RAG)", value=True)

cases = sorted(p.name for p in CASES.iterdir() if p.is_dir())
choice = st.selectbox("Start from a sample case", ["(paste my own)"] + cases, index=8)
if choice != "(paste my own)":
    spec = json.loads((CASES / choice / "case.json").read_text(encoding="utf-8"))
    default_code = (CASES / choice / "game.py").read_text(encoding="utf-8")
    default_tests = (CASES / choice / "test_game.py").read_text(encoding="utf-8")
    default_symptom = spec["symptom"]
else:
    default_code = default_tests = default_symptom = ""

symptom = st.text_input("What did you observe?", value=default_symptom)
col1, col2 = st.columns(2)
code = col1.text_area("game.py", value=default_code, height=320)
tests = col2.text_area("test_game.py (must import from game)", value=default_tests, height=320)

if st.button("Investigate 🔍", type="primary"):
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "game.py").write_text(code, encoding="utf-8")
        Path(tmp, "test_game.py").write_text(tests, encoding="utf-8")
        try:
            backend = make_backend(backend_choice)
        except Exception as e:  # e.g. missing SDK or credentials for "claude"
            st.error(f"Could not start the {backend_choice} backend: {e}")
            st.stop()
        agent = GlitchAgent(backend=backend, use_retrieval=use_retrieval)
        with st.spinner("Running tests, retrieving patterns, trying patches..."):
            result = agent.investigate(Path(tmp, "game.py"), Path(tmp, "test_game.py"), symptom)

    show = {"fixed": st.success, "no_bug_detected": st.success, "partial": st.warning,
            "needs_human_review": st.warning, "refused": st.error}[result.status]
    show(f"**{result.status}** (confidence {result.confidence}): {result.message}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Tests", result.tests_after or result.tests_before or "-")
    m2.metric("Iterations", result.iterations)
    m3.metric("Candidates tested", result.candidates_tried)
    for d in result.diagnosis:
        st.markdown(f"- {d}")
    if result.retrieved:
        st.caption("Retrieved patterns: " + ", ".join(f"{r['pattern']} ({r['support']})" for r in result.retrieved))
    if result.diff:
        st.subheader("Proposed patch (review before using)")
        st.code(result.diff, language="diff")
        st.download_button("Download fixed game.py", result.patched_source, file_name="game.py",
                           disabled=result.status != "fixed")
    with st.expander("Agent trace"):
        st.json(result.trace)
