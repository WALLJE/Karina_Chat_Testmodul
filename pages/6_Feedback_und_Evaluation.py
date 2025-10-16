import streamlit as st
from feedbackmodul import feedback_erzeugen
from module.feedback_ui import student_feedback
from module.sidebar import show_sidebar
from module.footer import copyright_footer
from module.gpt_feedback import speichere_gpt_feedback_in_supabase
from diagnostikmodul import aktualisiere_diagnostik_zusammenfassung
from module.offline import display_offline_banner, is_offline

show_sidebar()
copyright_footer()
display_offline_banner()

# Voraussetzungen prüfen
if "SYSTEM_PROMPT" not in st.session_state or "patient_name" not in st.session_state:
    st.warning("⚠️ Der Fall ist noch nicht geladen. Bitte beginne über die Startseite.")
    st.page_link("Karina_Chat_2.py", label="⬅ Zur Startseite")
    st.stop()

#if not st.session_state.get("final_diagnose") or not st.session_state.get("therapie_vorschlag"):
#    st.warning("⚠️ Bitte zuerst Diagnose und Therapie eingeben.")
#    st.stop()

aktualisiere_diagnostik_zusammenfassung()

if "student_evaluation_done" not in st.session_state:
    st.session_state["student_evaluation_done"] = False

feedback_text = st.session_state.get("final_feedback", "").strip()

if not feedback_text:
    diagnostik_eingaben = st.session_state.get("diagnostik_eingaben_kumuliert", "")
    gpt_befunde = st.session_state.get("gpt_befunde_kumuliert", "")
    koerper_befund = st.session_state.get("koerper_befund", "")
    final_diagnose = st.session_state.get("final_diagnose", "")
    therapie_vorschlag = st.session_state.get("therapie_vorschlag", "")
    diagnose_szenario = st.session_state.get("diagnose_szenario", "")
    user_ddx2 = st.session_state.get("user_ddx2", "")
    user_verlauf = "\n".join([
        msg["content"] for msg in st.session_state.messages
        if msg["role"] == "user"
    ])
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
            diagnose_szenario
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
                diagnose_szenario
            )

    st.session_state.final_feedback = feedback
    st.session_state["student_evaluation_done"] = False
    st.session_state.pop("feedback_row_id", None)
    feedback_text = feedback
    st.success("✅ Evaluation erstellt")
    if is_offline():
        st.info("🔌 Offline-Modus: Es wurde ein statisches Feedback verwendet.")

if feedback_text:
    if is_offline():
        st.info("🔌 Offline-Modus: Feedback wird nicht in Supabase gespeichert.")
    elif "feedback_row_id" not in st.session_state:
        speichere_gpt_feedback_in_supabase()

    st.markdown(feedback_text)
else:
    st.error("🚫 Das Abschluss-Feedback konnte nicht erstellt werden.")
    st.stop()

if st.session_state.final_feedback:
    student_feedback()

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
        mime="text/plain"
    )
else:
    st.info("💬 Der Download wird nach Abschluss der Evaluation freigeschaltet.")
