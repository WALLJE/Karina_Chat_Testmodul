from typing import Callable, Optional

import streamlit as st

from module.patient_language import get_patient_forms

def zeige_instruktionen_vor_start(lade_callback: Optional[Callable[[], None]] = None) -> None:
    """Blendet die Einstiegsinstruktionen ein und steuert den Ladeablauf."""

    st.session_state.setdefault("instruktion_bestätigt", False)
    st.session_state.setdefault("instruktion_loader_fertig", False)
    patient_forms = get_patient_forms()

    # Zur sicheren Anzeige merken wir uns den Namen frühzeitig.
    # Falls der Name noch nicht vorbereitet wurde, geben wir eine klare Hilfestellung aus,
    # damit während der Entwicklung sofort erkennbar ist, dass die Fallvorbereitung fehlt.
    patient_name = st.session_state.get("patient_name", "").strip()
    if not patient_name:
        st.info(
            "ℹ️ Der Patientenname ist noch nicht gesetzt. Bitte prüfen Sie, ob die Fallvorbereitung"
            " bereits abgeschlossen wird und aktivieren Sie bei Bedarf die Debug-Ausgaben im"
            " Lade-Callback."
        )
        # Platzhalter zur Anzeige im Fließtext; bewusst neutral gehalten, damit keine falschen Daten
        # suggeriert werden. Für eine detaillierte Analyse kann im Lade-Callback zusätzlich ein
        # st.write aktiviert werden (siehe Kommentar dort).
        patient_name = "der simulierten Patientin bzw. dem simulierten Patienten"

    if not st.session_state.instruktion_bestätigt:
        st.markdown(f"""
#### Instruktionen für Studierende:
Sie übernehmen die Rolle einer Ärztin oder eines Arztes im Gespräch mit {patient_forms.phrase("dat", adjective="virtuellen")} {patient_name}, {patient_forms.relative_pronoun()} sich in Ihrer hausärztlichen Sprechstunde vorstellt.
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
        if lade_callback and not st.session_state.instruktion_loader_fertig:
            try:
                # Die Fallvorbereitung läuft direkt unterhalb des Instruktionstextes,
                # damit der erste Spinner nicht auf einer leeren Seite erscheint.
                lade_callback()
            except Exception as exc:
                st.error(
                    "❌ Während der Vorbereitung ist ein Fehler aufgetreten. Bitte prüfen Sie die Debug-Hinweise im Kommentarbereich des Codes."
                )
                # Für die Fehlersuche kann temporär ein st.write im Ladecallback aktiviert werden.
                st.info(f"Technische Details: {exc}")
            else:
                st.session_state.instruktion_loader_fertig = True
        elif not lade_callback:
            # Falls kein Ladevorgang benötigt wird, ist der Button sofort verfügbar.
            st.session_state.instruktion_loader_fertig = True

        if st.session_state.instruktion_loader_fertig:
            st.page_link("pages/1_Anamnese.py", label="✅ Verstanden – weiter zur Anamnese")

        st.stop()

