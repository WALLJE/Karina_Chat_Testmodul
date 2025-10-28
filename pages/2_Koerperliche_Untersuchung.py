import streamlit as st
from datetime import datetime
import streamlit.components.v1 as components
from module.untersuchungsmodul import generiere_koerperbefund
from openai import RateLimitError
from module.sidebar import show_sidebar
from module.footer import copyright_footer
from module.offline import display_offline_banner, is_offline

copyright_footer()
show_sidebar()
display_offline_banner()

# Voraussetzungen prüfen
if (
    "diagnose_szenario" not in st.session_state or
    "patient_name" not in st.session_state or
    "patient_age" not in st.session_state or
    "patient_job" not in st.session_state or
    "diagnose_features" not in st.session_state
):
    st.warning("⚠️ Der Fall ist noch nicht geladen. Bitte beginne über die Startseite.")
    st.page_link("Karina_Chat_2.py", label="⬅ Zur Startseite")
    st.stop()

# Optional: Startzeit merken (z. B. für spätere Auswertung)
if "start_untersuchung" not in st.session_state:
    st.session_state.start_untersuchung = datetime.now()

# Körperlicher Befund generieren oder anzeigen

# Bedingung: mindestens eine Anamnesefrage gestellt
fragen_gestellt = any(m["role"] == "user" for m in st.session_state.get("messages", []))

if "koerper_befund" in st.session_state:
    st.success("✅ Körperliche Untersuchung erfolgt.")
    st.subheader("🔍 Befund")
    st.markdown(st.session_state.koerper_befund)

elif fragen_gestellt:
    if st.button("🩺 Untersuchung durchführen"):
        try:
            if is_offline():
                koerper_befund = generiere_koerperbefund(
                    st.session_state.get("openai_client"),
                    st.session_state.diagnose_szenario,
                    st.session_state.diagnose_features,
                    st.session_state.get("koerper_befund_tip", "")
                )
            else:
                with st.spinner(f"{st.session_state.patient_name} wird untersucht..."):
                    koerper_befund = generiere_koerperbefund(
                        st.session_state["openai_client"],
                        st.session_state.diagnose_szenario,
                        st.session_state.diagnose_features,
                        st.session_state.get("koerper_befund_tip", "")
                    )
            st.session_state.koerper_befund = koerper_befund
            if is_offline():
                st.info("🔌 Offline-Befund geladen. Sobald der Online-Modus aktiv ist, kannst du einen KI-generierten Befund abrufen.")
            st.rerun()
        except RateLimitError:
            st.error("🚫 Die Untersuchung konnte nicht erstellt werden. Die OpenAI-API ist derzeit überlastet.")
else:
    st.subheader("🩺 Untersuchung")
    st.button("Untersuchung durchführen", disabled=True)
    st.info(f"Zuerst bitte mit {st.session_state.patient_name} sprechen.", icon="🔒")
    st.page_link("pages/1_Anamnese.py", label="Zurück zur Anamnese", icon="⬅")
    
# Verlauf sichern (optional für spätere Analyse)
if "untersuchung_done" not in st.session_state:
    st.session_state.untersuchung_done = True

# Trennlinie zum Navigationslink
st.markdown("---")

# Weiter-Link zur Diagnostik
# Hinweis: "href='/Diagnostik'" sorgt für internen Seitenwechsel, nicht für neues Fenster
st.page_link(
    "pages/4_Diagnostik_und_Befunde.py",
    label="Weiter zur Diagnostik",
    icon="🧪",
    disabled="koerper_befund" not in st.session_state
)

