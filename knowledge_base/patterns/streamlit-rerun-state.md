---
id: streamlit-rerun-state
title: Streamlit rerun resets plain variables
repair: none
---
# Streamlit rerun resets plain variables

## Symptoms
The secret number changes every time the Submit button is clicked. Counters reset to zero after each interaction. The game cannot be won because the target keeps moving.

## Root cause
Streamlit reruns the whole script top to bottom on every widget interaction. Plain Python variables are recreated each run; only st.session_state survives between reruns.

## Fix recipe
Store the secret, attempts, score, status, and history in st.session_state and initialize each one only if the key is missing. This is a UI-layer fix and usually cannot be verified by pure unit tests, so flag it for human review.
