"""Evaluation und Download der Simulationsergebnisse.

Diese Seite bildet den zweiten Schritt nach dem automatischen Feedback. Studierende
können hier ihre Evaluation abgeben und – nach Abschluss – das vollständige Protokoll
herunterladen.
"""

import streamlit as st

from module.fallverwaltung import reset_fall_session_state
from module.feedback_ui import student_feedback
from module.footer import copyright_footer
from module.navigation import redirect_to_start_page
from module.offline import display_offline_banner
from module.sidebar import show_sidebar


# Konsistente Einbindung von Sidebar, Footer und Offline-Hinweis.
copyright_footer()
show_sidebar()
display_offline_banner()


def _pruefe_voraussetzungen() -> None:
    """Stellt sicher, dass das Feedback bereits erstellt wurde."""

    if not st.session_state.get("final_feedback", "").strip():
        redirect_to_start_page(
            "⚠️ Bitte sieh dir zunächst das automatische Feedback an und folge der vorgesehenen Navigation von der Startseite."
        )


def _zeige_downloadbereich() -> None:
    """Baut den bekannten Downloadbereich auf."""

    st.markdown("---")
    st.subheader("📄 Download")

    if st.session_state.get("final_feedback") and st.session_state.get("student_evaluation_done"):
        protokoll = ""

        protokoll += f"Simuliertes Krankheitsbild: {st.session_state.diagnose_szenario}\n\n"

        protokoll += "---\n💬 Gesprächsverlauf (nur Fragen des Studierenden):\n"
        for msg in st.session_state.messages[1:]:
            rolle = st.session_state.patient_name if msg["role"] == "assistant" else "Du"
            protokoll += f"{rolle}: {msg['content']}\n"

        if "koerper_befund" in st.session_state:
            protokoll += "\n---\n Körperlicher Untersuchungsbefund:\n"
            protokoll += st.session_state.koerper_befund + "\n"

        if "user_ddx2" in st.session_state:
            protokoll += "\n---\n Erhobene Differentialdiagnosen:\n"
            protokoll += st.session_state.user_ddx2 + "\n"

        if "diagnostik_eingaben_kumuliert" in st.session_state:
            protokoll += "\n---\n Geplante diagnostische Maßnahmen (alle Termine):\n"
            protokoll += st.session_state.diagnostik_eingaben_kumuliert + "\n"

        if "gpt_befunde_kumuliert" in st.session_state:
            protokoll += "\n---\n📄 Ergebnisse der diagnostischen Maßnahmen:\n"
            protokoll += st.session_state.gpt_befunde_kumuliert + "\n"

        if "final_diagnose" in st.session_state:
            protokoll += "\n---\n Finale Diagnose:\n"
            protokoll += st.session_state.final_diagnose + "\n"

        if "therapie_vorschlag" in st.session_state:
            protokoll += "\n---\n Therapiekonzept:\n"
            protokoll += st.session_state.therapie_vorschlag + "\n"

        protokoll += "\n---\n Strukturierte Rückmeldung:\n"
        protokoll += st.session_state.final_feedback + "\n"

        st.download_button(
            label="⬇️ Gespräch & Feedback herunterladen",
            data=protokoll,
            file_name="karina_chatprotokoll.txt",
            mime="text/plain",
        )
    else:
        st.info("💬 Der Download wird nach Abschluss der Evaluation freigeschaltet.")


def _bereinige_session_state_fuer_neustart() -> None:
    """Entfernt alle fallbezogenen Werte, damit ein neues Szenario sauber starten kann."""

    # Wir verwenden den zentralen Reset-Helfer, um sämtliche fallrelevanten Werte aus dem
    # Session-State zu löschen. So vermeiden wir veraltete Befunde oder Chatverläufe.
    reset_fall_session_state()

    # Zusätzlich entfernen wir Steuerflags der Startseite, damit die Instruktionen und
    # Ladeindikatoren beim nächsten Besuch erneut angezeigt werden. Für Debugging kann
    # hier bei Bedarf temporär ``st.write(st.session_state)`` aktiviert werden.
    for schluessel in (
        "fall_vorbereitung_abgeschlossen",
        "instruktion_bestätigt",
        "instruktion_loader_fertig",
    ):
        st.session_state.pop(schluessel, None)


def _zeige_neustart_button() -> None:
    """Stellt einen deutlich markierten Button bereit, um ein frisches Szenario zu starten."""

    st.markdown("---")
    if st.button("🔄 Neues Szenario starten", type="primary"):
        # Zuerst wird der Session-State bereinigt, damit keine Datenreste den neuen Fall
        # beeinflussen. Falls unerwartete Werte erhalten bleiben, kann oberhalb des Buttons
        # kurzzeitig eine Debug-Ausgabe ergänzt werden.
        _bereinige_session_state_fuer_neustart()

        # Danach leiten wir direkt auf die Startseite zurück. Streamlit stellt sicher,
        # dass der Multipage-Mechanismus korrekt greift und die Fallvorbereitung erneut
        # ausgeführt wird.
        st.switch_page("Karina_Chat_2.py")


def main() -> None:
    """Steuert die Anzeige der Evaluation sowie den Downloadbereich."""

    _pruefe_voraussetzungen()

    student_feedback()

    _zeige_downloadbereich()
    _zeige_neustart_button()


if __name__ == "__main__":  # pragma: no cover - Streamlit startet die Seite selbst
    main()
