import streamlit as st

from module.patient_language import get_patient_forms

def zeige_instruktionen_vor_start():
    st.session_state.setdefault("instruktion_bestätigt", False)
    patient_forms = get_patient_forms()

    if not st.session_state.instruktion_bestätigt:
        st.markdown(f"""
#### Instruktionen für Studierende:
Sie übernehmen die Rolle einer Ärztin oder eines Arztes im Gespräch mit {patient_forms.phrase("dat", adjective="virtuellen")} {st.session_state.patient_name}, {patient_forms.relative_pronoun()} sich in Ihrer hausärztlichen Sprechstunde vorstellt.
Ihr Ziel ist es, durch gezielte Anamnese und klinisches Denken eine Verdachtsdiagnose zu stellen sowie ein sinnvolles diagnostisches und therapeutisches Vorgehen zu entwickeln.

#### 🔍 Ablauf:

1. **Stellen Sie jederzeit Fragen an {patient_forms.phrase("acc")}** – geben Sie diese im Chat ein.
2. Wenn Sie genug Informationen gesammelt haben, führen Sie eine **körperliche Untersuchung** durch.
3. Formulieren Sie Ihre **Differentialdiagnosen** und wählen Sie geeignete **diagnostische Maßnahmen**.
4. Nach Erhalt der Befunde treffen Sie Ihre **endgültige Diagnose** und machen einen **Therapievorschlag**.
5. Abschließend erhalten Sie ein **automatisches Feedback** zu Ihrem Vorgehen.

> 💬 **Hinweis:** Sie können {patient_forms.phrase("acc")} auch nach der ersten Diagnostik weiter befragen –
z. B. bei neuen Verdachtsmomenten oder zur gezielten Klärung offener Fragen.

Im Wartezimmer sitzen weitere {patient_forms.plural_phrase()} mit anderen Krankheitsbildern, die Sie durch einen erneuten Aufruf der App kennenlernen können.

---
- **Überprüfen Sie alle Angaben und Hinweise der Kommunikation auf Richtigkeit.** 
- Die Anwendung sollte aufgrund ihrer Limitationen nur unter ärztlicher Supervision genutzt werden; Sie können bei Fragen und Unklarheiten den Chatverlauf in einer Text-Datei speichern.

---
""")
        st.page_link("pages/1_Anamnese.py", label="✅ Verstanden – weiter zur Anamnese")
        st.stop ()

