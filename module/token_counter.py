import streamlit as st

def init_token_counters():
    """Initialisiert die Token-Zähler einmal pro Session."""
    if "token_sums" not in st.session_state:
        st.session_state["token_sums"] = {"prompt": 0, "completion": 0, "total": 0}

def add_usage(prompt_tokens: int, completion_tokens: int, total_tokens: int):
    """Addiert die Tokenwerte auf die Session-Summen."""
    if "token_sums" not in st.session_state:
        init_token_counters()
    st.session_state["token_sums"]["prompt"]    += int(prompt_tokens or 0)
    st.session_state["token_sums"]["completion"]+= int(completion_tokens or 0)
    st.session_state["token_sums"]["total"]     += int(total_tokens or 0)

def get_token_sums():
    """Gibt die aktuellen Summen zurück."""
    if "token_sums" not in st.session_state:
        init_token_counters()
    return (
        st.session_state["token_sums"]["prompt"],
        st.session_state["token_sums"]["completion"],
        st.session_state["token_sums"]["total"]
    )
