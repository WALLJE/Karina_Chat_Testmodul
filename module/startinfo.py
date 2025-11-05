from typing import Callable, Optional

import streamlit as st

from module.patient_language import get_patient_forms


def zeige_instruktionen_vor_start(lade_callback: Optional[Callable[[], None]] = None) -> None:
    """Blendet die Einstiegsinstruktionen ein und steuert den Ladeablauf."""

    st.session_state.setdefault("instruktion_bestätigt", False)
    st.session_state.setdefault("instruktion_loader_fertig", False)
    # Wir verwenden Platzhalter-Container, damit sich die Inhalte nach Abschluss des
    # Ladecallbacks aktualisieren lassen, ohne dass der Seitenaufbau neu strukturiert wird.
    instruktionen_placeholder = st.empty()
    ladebereich = st.container()
    fortsetzen_placeholder = st.empty()

    def schreibe_instruktionen() -> None:
        """Erzeugt den Instruktionstext mit dynamischen Personenangaben."""

        # Wir holen die sprachlichen Formen innerhalb der Funktion, damit bei jedem Aufruf
        # der aktuelle Personenstatus (Geschlecht und Name) berücksichtigt wird. Während der
        # Fallvorbereitung wird ``patient_gender`` häufig erst gesetzt – so vermeiden wir,
        # dass zuvor gecachte Formen beibehalten werden.
        patient_forms = get_patient_forms()
        patient_name = st.session_state.get("patient_name", "").strip()
        if patient_name:
            patient_intro = (
                "Sie übernehmen die Rolle einer Ärztin oder eines Arztes im Gespräch mit "
                f"{patient_name}, {patient_forms.relative_pronoun()} sich in Ihrer hausärztlichen Sprechstunde vorstellt."
            )
        else:
            # Solange der Name noch nicht bekannt ist, verwenden wir eine allgemein verständliche Formulierung.
            # Sobald die Fallvorbereitung abgeschlossen wurde, aktualisieren wir den Text automatisch mit dem konkreten Namen.
            patient_intro = (
                "Sie übernehmen die Rolle einer Ärztin oder eines Arztes im Gespräch mit einer simulierten Patientin "
                f"bzw. einem simulierten Patienten, {patient_forms.relative_pronoun()} sich in Ihrer hausärztlichen Sprechstunde vorstellt."
            )

        instruktionen_placeholder.markdown(
            f"""
#### Instruktionen für Studierende:
{patient_intro}
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
"""
        )

    schreibe_instruktionen()

    if lade_callback and not st.session_state.instruktion_loader_fertig:
        with ladebereich:
            try:
                # Die Fallvorbereitung läuft direkt unterhalb des Instruktionstextes,
                # damit der erste Spinner nicht auf einer leeren Seite erscheint.
                lade_callback()
            except Exception as exc:
                st.error(
                    "❌ Während der Vorbereitung ist ein Fehler aufgetreten. Bitte prüfen Sie die Debug-Hinweise im Kommentarbereich des Codes."
                )
                st.info("Tipp: Aktivieren Sie temporär zusätzliche st.write-Ausgaben im Lade-Callback, um den Fehler einzugrenzen.")
                st.info(f"Technische Details: {exc}")
            else:
                st.session_state.instruktion_loader_fertig = True
                # Nach erfolgreicher Vorbereitung steht der Name zur Verfügung und kann in den
                # Instruktionen angezeigt werden.
                schreibe_instruktionen()
    elif st.session_state.get("fall_vorbereitung_abgeschlossen"):
        # Wurde der Ladevorgang bereits abgeschlossen, bleibt der Hinweis sichtbar.
        with ladebereich:
            # Wir greifen hier erneut auf den Namen zu, um den Übergang möglichst patientenzentriert zu formulieren.
            patient_name = st.session_state.get("patient_name", "").strip()
            if patient_name:
                start_hinweis = f"Fallvorbereitung abgeschlossen. Beginnen Sie das Gespräch mit {patient_name}."
            else:
                start_hinweis = "Fallvorbereitung abgeschlossen. Beginnen Sie das Gespräch mit der simulierten Patientin oder dem Patienten."
            st.success(start_hinweis)
    elif not lade_callback:
        # Falls kein Ladevorgang benötigt wird, ist der Button sofort verfügbar.
        st.session_state.instruktion_loader_fertig = True

    if st.session_state.instruktion_loader_fertig:
        # Sobald die Vorbereitung abgeschlossen ist, stellen wir ein deutlich sichtbares "OK"-Feld bereit,
        # das den eigentlichen Fallstart einleitet. Durch die Verwendung von ``page_link`` wird direkt
        # die nächste Seite (Anamnese) geöffnet, wodurch die Studierenden nahtlos in die Konsultation
        # übergehen können.
        fortsetzen_placeholder.page_link("pages/1_Anamnese.py", label="OK")

    st.stop()

