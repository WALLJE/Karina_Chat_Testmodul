"""Hilfsfunktionen zur Verwaltung des Feedback-Modus (ChatGPT vs. AMBOSS).

Die Kommentare sind bewusst ausführlich, damit zukünftige Anpassungen leichter
nachvollzogen werden können. Der Modus wird zentral bestimmt und in der
``st.session_state``-Struktur abgelegt, sodass alle Komponenten denselben Wert
verwenden. Standardmäßig erfolgt eine zufällige Auswahl zwischen reinem
ChatGPT-Feedback und einer Variante, die zusätzlich AMBOSS-Inhalte einbezieht.
"""

from __future__ import annotations

import random
from typing import Optional

import streamlit as st

# Konstante Bezeichner, die überall in der Anwendung wiederverwendet werden.
# Durch die zentrale Definition vermeiden wir Tippfehler und behalten die
# mögliche Werte-Menge im Blick. Wenn in Zukunft weitere Modi hinzukommen,
# können sie hier ergänzt werden.
FEEDBACK_MODE_CHATGPT = "ChatGPT"
FEEDBACK_MODE_AMBOSS_CHATGPT = "Amboss_ChatGPT"

# Session-State-Schlüssel, die für die Modussteuerung verwendet werden.
SESSION_KEY_EFFECTIVE_MODE = "feedback_mode"
SESSION_KEY_OVERRIDE = "feedback_mode_override"

# Liste der verfügbaren Modi – derzeit genau zwei. Die Liste hilft bei der
# Zufallsauswahl und dient zusätzlich als Validierungsgrundlage.
_AVAILABLE_MODES = [FEEDBACK_MODE_CHATGPT, FEEDBACK_MODE_AMBOSS_CHATGPT]


def _is_valid_mode(value: Optional[str]) -> bool:
    """Prüft, ob ein Wert einem der definierten Modi entspricht."""

    return value in _AVAILABLE_MODES


def determine_feedback_mode() -> str:
    """Ermittelt den aktiven Feedback-Modus und legt ihn im Session State ab.

    Ablauf:
    1. Falls im Session State eine Admin-Übersteuerung hinterlegt ist, wird
       diese direkt übernommen.
    2. Ansonsten wird geprüft, ob bereits ein Modus für die aktuelle Sitzung
       gespeichert wurde. Wenn ja, wird er beibehalten.
    3. Liegt noch kein Modus vor, erfolgt eine zufällige Auswahl.

    Jeder Pfad speichert den finalen Modus unter ``SESSION_KEY_EFFECTIVE_MODE``.
    Auf diese Weise können andere Module (z. B. Supabase-Speicherung oder UI)
    denselben Wert nutzen, ohne die Entscheidung erneut treffen zu müssen.
    """

    override = st.session_state.get(SESSION_KEY_OVERRIDE)
    if _is_valid_mode(override):
        mode = override
    else:
        current = st.session_state.get(SESSION_KEY_EFFECTIVE_MODE)
        if _is_valid_mode(current):
            mode = current
        else:
            mode = random.choice(_AVAILABLE_MODES)

    st.session_state[SESSION_KEY_EFFECTIVE_MODE] = mode
    return mode


def reset_random_mode() -> None:
    """Entfernt den gespeicherten Modus, damit bei der nächsten Anfrage neu gelost wird."""

    st.session_state.pop(SESSION_KEY_EFFECTIVE_MODE, None)


def set_mode_override(mode: Optional[str]) -> None:
    """Hinterlegt eine optionale Admin-Übersteuerung.

    Wird ``None`` übergeben, entfernt die Funktion die Übersteuerung. Bei einem
    unbekannten Wert wird eine ``ValueError`` ausgelöst, damit Fehler frühzeitig
    auffallen und nicht stillschweigend ignoriert werden.
    """

    if mode is None:
        st.session_state.pop(SESSION_KEY_OVERRIDE, None)
        return

    if not _is_valid_mode(mode):
        raise ValueError(
            "Ungültiger Feedback-Modus. Erlaubt sind: " + ", ".join(_AVAILABLE_MODES)
        )

    st.session_state[SESSION_KEY_OVERRIDE] = mode
