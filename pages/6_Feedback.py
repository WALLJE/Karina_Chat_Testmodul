"""Feedback-Seite der Simulation.

Diese Datei kapselt ausschließlich die Darstellung und Generierung des automatischen
Feedbacks nach Abschluss von Diagnose und Therapie. Die eigentliche Evaluation der
Studierenden erfolgt auf der nachgelagerten Seite `7_Evaluation_und_Download.py`.
"""

import streamlit as st

from diagnostikmodul import aktualisiere_diagnostik_zusammenfassung
from feedbackmodul import feedback_erzeugen
from module.footer import copyright_footer
from module.gpt_feedback import speichere_gpt_feedback_in_supabase
from module.offline import display_offline_banner, is_offline
from module.sidebar import show_sidebar


# Die Sidebar und der Footer werden identisch zu den übrigen Seiten dargestellt, damit
# die Nutzerführung konsistent bleibt.
copyright_footer()
show_sidebar()
display_offline_banner()


def _pruefe_voraussetzungen() -> None:
    """Validiert alle notwendigen Session-State-Einträge.

    Die Feedbackgenerierung setzt voraus, dass der Fall vollständig geladen wurde.
    Es wird absichtlich *nicht* auf Diagnose/Therapie geprüft, weil die Navigation
    diese Seite ohnehin nur freigibt, wenn beide Eingaben vorliegen. So vermeiden wir
    doppelte Abbruchbedingungen und erleichtern das Debugging.
    """

    if "SYSTEM_PROMPT" not in st.session_state or "patient_name" not in st.session_state:
        st.warning(
            "⚠️ Der Fall ist noch nicht geladen. Bitte beginne über die Startseite."
        )
        st.page_link("Karina_Chat_2.py", label="⬅ Zur Startseite")
        st.stop()


def _generiere_feedback() -> str:
    """Erzeugt oder lädt das finale Feedback aus dem Session-State.

    Falls noch kein Feedback existiert, werden alle für das LLM relevanten Daten
    zusammengetragen, anschließend erfolgt die Generierung – offline mit dem
    vorbereiteten Stub, online via OpenAI. Nach erfolgreicher Erstellung wird der
    Session-State aktualisiert und die Evaluation zurückgesetzt, sodass Studierende
    erneut Feedback abgeben können.
    """

    feedback_text = st.session_state.get("final_feedback", "").strip()
    if feedback_text:
        return feedback_text

    diagnostik_eingaben = st.session_state.get("diagnostik_eingaben_kumuliert", "")
    gpt_befunde = st.session_state.get("gpt_befunde_kumuliert", "")
    koerper_befund = st.session_state.get("koerper_befund", "")
    final_diagnose = st.session_state.get("final_diagnose", "")
    therapie_vorschlag = st.session_state.get("therapie_vorschlag", "")
    diagnose_szenario = st.session_state.get("diagnose_szenario", "")
    user_ddx2 = st.session_state.get("user_ddx2", "")
    user_verlauf = "\n".join(
        msg["content"] for msg in st.session_state.get("messages", []) if msg["role"] == "user"
    )
    anzahl_termine = st.session_state.get("diagnostik_runden_gesamt", 1)

    if is_offline():
        feedback = feedback_erzeugen(
            st.session_state.get("openai_client"),
            final_diagnose,
            therapie_vorschlag,
            user_ddx2,
            diagnostik_eingaben,
            gpt_befunde,
            koerper_befund,
            user_verlauf,
            anzahl_termine,
            diagnose_szenario,
        )
    else:
        with st.spinner("⏳ Abschluss-Feedback wird erstellt..."):
            feedback = feedback_erzeugen(
                st.session_state["openai_client"],
                final_diagnose,
                therapie_vorschlag,
                user_ddx2,
                diagnostik_eingaben,
                gpt_befunde,
                koerper_befund,
                user_verlauf,
                anzahl_termine,
                diagnose_szenario,
            )

    st.session_state.final_feedback = feedback
    st.session_state["student_evaluation_done"] = False
    st.session_state.pop("feedback_row_id", None)
    return feedback


def _zeige_feedback(feedback_text: str) -> None:
    """Stellt das Feedback dar und synchronisiert Supabase bei Bedarf."""

    if is_offline():
        st.info("🔌 Offline-Modus: Feedback wird nicht in Supabase gespeichert.")
    elif "feedback_row_id" not in st.session_state:
        # Sobald das Feedback erstmals angezeigt wird, erfolgt das Persistieren.
        speichere_gpt_feedback_in_supabase()

    st.subheader("📋 Automatisches Feedback")
    st.markdown(feedback_text)


def main() -> None:
    """Zentrale Steuermethode für die Feedback-Seite."""

    _pruefe_voraussetzungen()
    aktualisiere_diagnostik_zusammenfassung()

    if "student_evaluation_done" not in st.session_state:
        st.session_state["student_evaluation_done"] = False

    feedback_text = _generiere_feedback()
    if not feedback_text:
        st.error("🚫 Das Abschluss-Feedback konnte nicht erstellt werden.")
        st.stop()

    _zeige_feedback(feedback_text)

    st.markdown("---")
    st.page_link(
        "pages/7_Evaluation_und_Download.py",
        label="Weiter zur Evaluation",
        icon="📊",
    )
    st.caption(
        "💡 Die Evaluation ist für die Weiterentwicklung und wissenschaftliche Auswertung extrem wichtig."
    )


if __name__ == "__main__":  # pragma: no cover - Streamlit startet die Seite selbst
    main()
