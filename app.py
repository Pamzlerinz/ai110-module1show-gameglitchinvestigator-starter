import os
import random
import streamlit as st

from logic_utils import (
    get_range_for_difficulty,
    parse_guess,
    check_guess,
    get_hint_message,
    update_score,
)

st.set_page_config(page_title="Glitchy Guesser", page_icon="🎮")

# Small style layer on top of the theme in .streamlit/config.toml. Colors use
# translucent tints so they read well in both light and dark mode.
st.markdown(
    """
    <style>
    .hero { text-align: center; padding: 0.5rem 0 1rem; }
    .hero h1 { margin-bottom: 0.25rem; }
    .hero p { opacity: 0.75; font-size: 1.05rem; margin: 0; }
    .chips { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.25rem; }
    .chip {
        padding: 0.3rem 0.75rem; border-radius: 999px; font-weight: 600;
        border: 1px solid rgba(128, 128, 128, 0.35);
    }
    .chip.high { background: rgba(239, 68, 68, 0.15); }
    .chip.low  { background: rgba(59, 130, 246, 0.15); }
    .chip.win  { background: rgba(34, 197, 94, 0.20); }
    .chip.bad  { background: rgba(128, 128, 128, 0.15); opacity: 0.8; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <h1>🎮 Game Glitch Investigator</h1>
      <p>The bugs have been squashed. Can you find the secret number?</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.header("Settings")

difficulty = st.sidebar.selectbox(
    "Difficulty",
    ["Easy", "Normal", "Hard"],
    index=1,
)

attempt_limit_map = {
    "Easy": 6,
    "Normal": 8,
    "Hard": 5,
}
attempt_limit = attempt_limit_map[difficulty]

low, high = get_range_for_difficulty(difficulty)

st.sidebar.caption(f"Range: {low} to {high}")
st.sidebar.caption(f"Attempts allowed: {attempt_limit}")
st.sidebar.info("🕵️ Want the AI to hunt glitches for you? Open the **Glitch Agent** page above.")

if "secret" not in st.session_state:
    st.session_state.secret = random.randint(low, high)

if "attempts" not in st.session_state:
    # FIX: was initialized to 1, which made "Attempts left" undercount by
    # one before the player had even guessed. Verified by checking the
    # sidebar counter on a fresh game: it now starts at the full limit.
    st.session_state.attempts = 0

if "score" not in st.session_state:
    st.session_state.score = 0

if "status" not in st.session_state:
    st.session_state.status = "playing"

if "history" not in st.session_state:
    st.session_state.history = []

# Debug info shows the secret, so it is hidden from players. Developers can
# turn it on by starting the app with the GLITCH_DEBUG=1 environment variable.
if os.environ.get("GLITCH_DEBUG") == "1":
    with st.expander("Developer Debug Info"):
        st.write("Secret:", st.session_state.secret)
        st.write("Attempts:", st.session_state.attempts)
        st.write("Score:", st.session_state.score)
        st.write("Difficulty:", difficulty)
        st.write("History:", st.session_state.history)

# Placeholders are drawn now but filled at the end of the script, after the
# guess has been counted, so the numbers on screen are never one guess behind.
stats_slot = st.empty()

with st.container(border=True):
    st.markdown(f"#### Guess a number between {low} and {high}")
    # The guess box and Submit button live in a form so pressing Enter in the
    # box submits the guess, same as clicking the button. clear_on_submit
    # empties the box after each guess so the player can type the next one.
    with st.form(key=f"guess_form_{difficulty}", border=False, clear_on_submit=True):
        raw_guess = st.text_input(
            "Your guess",
            key=f"guess_input_{difficulty}",
            placeholder=f"Type a number from {low} to {high} and press Enter",
        )
        btn_col, status_col = st.columns([1, 2], vertical_alignment="center")
        with btn_col:
            submit = st.form_submit_button(
                "Submit Guess 🚀", type="primary", width="stretch"
            )
        with status_col:
            status_slot = st.empty()
    progress_slot = st.empty()

feedback_slot = st.container()
history_slot = st.empty()

col1, col2 = st.columns(2)
with col1:
    new_game = st.button("New Game 🔁", width="stretch")
with col2:
    show_hint = st.checkbox("Show hint", value=True)


def guess_chip(entry):
    """One past guess as a colored chip with an arrow pointing to the secret."""
    if not isinstance(entry, int):
        return f'<span class="chip bad">⚠️ {entry or "blank"}</span>'
    outcome = check_guess(entry, st.session_state.secret)
    if outcome == "Win":
        return f'<span class="chip win">✅ {entry}</span>'
    if outcome == "Too High":
        return f'<span class="chip high">{entry} ⬇️</span>'
    return f'<span class="chip low">{entry} ⬆️</span>'


def render_dashboard():
    attempts = st.session_state.attempts
    left = attempt_limit - attempts

    with stats_slot.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Difficulty", difficulty)
        c2.metric("Attempts left", f"{left} / {attempt_limit}")
        c3.metric("Score", st.session_state.score)

    text = f"**Attempts left: {left}** of {attempt_limit}"
    if st.session_state.history:
        text += f" · Last guess: **{st.session_state.history[-1]}**"
    status_slot.markdown(text)

    progress_slot.progress(
        min(attempts / attempt_limit, 1.0),
        text=f"{attempts} of {attempt_limit} attempts used",
    )

    if st.session_state.history:
        chips = "".join(guess_chip(e) for e in st.session_state.history)
        history_slot.markdown(
            f"**Your guesses** (⬇️ go lower, ⬆️ go higher)"
            f'<div class="chips">{chips}</div>',
            unsafe_allow_html=True,
        )


if new_game:
    # FIX: status/score/history were never reset here, so the "already
    # won"/"game over" branch below trapped the player forever, and the
    # new secret ignored the selected difficulty's range. Fixed with
    # Claude in agent mode; verified by winning a game, clicking New Game,
    # and confirming a fresh round actually starts.
    st.session_state.attempts = 0
    st.session_state.secret = random.randint(low, high)
    st.session_state.score = 0
    st.session_state.status = "playing"
    st.session_state.history = []
    st.success("New game started.")
    st.rerun()

if st.session_state.status != "playing":
    render_dashboard()
    with feedback_slot:
        if st.session_state.status == "won":
            st.success("You already won. Start a new game to play again.")
        else:
            st.error("Game over. Start a new game to try again.")
    st.stop()

if submit:
    st.session_state.attempts += 1

    ok, guess_int, err = parse_guess(raw_guess)

    with feedback_slot:
        if not ok:
            st.session_state.history.append(raw_guess)
            st.error(err)
        else:
            st.session_state.history.append(guess_int)

            # FIX: this used to alternate the secret between int and str every
            # other attempt before comparing, which is what broke the hints.
            # The secret passed to check_guess is now always the plain int
            # stored in session state.
            outcome = check_guess(guess_int, st.session_state.secret)
            message = get_hint_message(outcome)

            if show_hint:
                st.warning(message)

            st.session_state.score = update_score(
                current_score=st.session_state.score,
                outcome=outcome,
                attempt_number=st.session_state.attempts,
                attempt_limit=attempt_limit,
            )

            if outcome == "Win":
                st.balloons()
                st.session_state.status = "won"
                st.success(
                    f"You won! The secret was {st.session_state.secret}. "
                    f"Final score: {st.session_state.score}"
                )
            else:
                if st.session_state.attempts >= attempt_limit:
                    st.session_state.status = "lost"
                    st.error(
                        f"Out of attempts! "
                        f"The secret was {st.session_state.secret}. "
                        f"Score: {st.session_state.score}"
                    )

render_dashboard()

st.divider()
st.caption("Built by an AI that claims this code is production-ready.")
