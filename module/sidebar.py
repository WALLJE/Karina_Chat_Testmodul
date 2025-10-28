import streamlit as st
import os
import random
from PIL import Image


def show_sidebar():
    # DEBUG
    # st.sidebar.write("🧪 DEBUG: keys in session_state:", list(st.session_state.keys()))

    with st.sidebar:
        # st.markdown("### Patientin")

        def bestimme_bilder_ordner():
            geschlecht = str(st.session_state.get("patient_gender", "")).strip().lower()
            try:
                alter = int(st.session_state.get("patient_age", ""))
            except (TypeError, ValueError):
                alter = None

            if alter is None or geschlecht not in {"m", "w"}:
                return "pics"

            if geschlecht == "w":
                if alter <= 30:
                    unterordner = "junior_female"
                elif alter <= 47:
                    unterordner = "mid_female"
                else:
                    unterordner = "senior_female"
            else:  # männlich
                if alter <= 30:
                    unterordner = "junior_male"
                elif alter <= 47:
                    unterordner = "mid_male"
                else:
                    unterordner = "senior_male"

            return os.path.join("pics", unterordner)

        def lade_gueltige_bilder(ordnerpfad):
            bilder = []
            if os.path.isdir(ordnerpfad):
                for eintrag in os.listdir(ordnerpfad):
                    if eintrag.lower().endswith(".png"):
                        pfad = os.path.join(ordnerpfad, eintrag)
                        try:
                            with Image.open(pfad) as img:
                                img.verify()
                            bilder.append(pfad)
                        except Exception:
                            continue
            return bilder

        pic_dir = bestimme_bilder_ordner()
        valid_images = lade_gueltige_bilder(pic_dir)

        if not valid_images and pic_dir != "pics":
            valid_images = lade_gueltige_bilder("pics")

        if valid_images:
            if (
                "patient_logo" not in st.session_state
                or st.session_state.patient_logo not in valid_images
            ):
                st.session_state.patient_logo = random.choice(valid_images)


        try:
            st.image(st.session_state.patient_logo, width=160)
        except Exception as e:
            st.warning(f"⚠️ Bild konnte nicht geladen werden: {e}")

        if all(k in st.session_state for k in ["patient_name", "patient_age"]):
            patient_text = f"**{st.session_state.patient_name} ({st.session_state.patient_age})**"
            if "patient_job" in st.session_state:
                patient_text += f", {st.session_state.patient_job}"
            st.markdown(patient_text)

        st.markdown("### Navigation")
        st.page_link("pages/1_Anamnese.py", label="Anamnese", icon="💬")

# Nur wenn mind. eine Frage gestellt wurde (Chatverlauf existiert)
        if "messages" in st.session_state and any(m["role"] == "user" for m in st.session_state["messages"]):
            st.page_link("pages/2_Koerperliche_Untersuchung.py", label="Untersuchung", icon="🩺")
    
        # Nur wenn Untersuchung erfolgt ist
        if "koerper_befund" in st.session_state:
            st.page_link("pages/4_Diagnostik_und_Befunde.py", label="Diagnostik", icon="🧪")
    
        # Nur wenn Diagnostik abgeschlossen (Verdachtsdiagnosen vorliegen)
        if (
            "user_diagnostics" in st.session_state and
            "user_ddx2" in st.session_state
        ):
            st.page_link("pages/5_Diagnose_und_Therapie.py", label="Diagnose und Therapie", icon="💊")
    
        # Nur wenn finale Diagnose gesetzt
        if (
            "final_diagnose" in st.session_state and
            "therapie_vorschlag" in st.session_state
        ):
            st.page_link("pages/6_Feedback_und_Evaluation.py", label="📝 Feedback & Download")

        st.page_link("pages/20_Impressum.py", label="Impressum und Hinweise", icon="📰")

        if st.session_state.get("is_admin"):
            st.page_link("pages/21_Admin.py", label="🔑 Adminbereich")

        st.markdown("---")
        st.caption("🔒 Weitere Seiten erscheinen automatisch, sobald diagnostische Schritte abgeschlossen wurden.")

