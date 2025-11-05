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
            # Der Hinweis zur abgeschlossenen Vorbereitung soll laut Vorgabe sachlich bleiben,
            # daher verzichten wir auf grüne Hervorhebungen wie ``st.success`` und geben den
            # Text bewusst neutral aus.
            st.markdown(f"**{start_hinweis}**")
    elif not lade_callback:
        # Falls kein Ladevorgang benötigt wird, ist der Button sofort verfügbar.
        st.session_state.instruktion_loader_fertig = True

    if st.session_state.instruktion_loader_fertig:
        # Sobald die Vorbereitung abgeschlossen ist, stellen wir ein deutlich sichtbares "OK"-Feld bereit,
        # das den eigentlichen Fallstart einleitet. Über ``st.switch_page`` springen wir direkt in die
        # Anamnese-Seite, damit der Übergang für die Studierenden nahtlos erfolgt.
        with fortsetzen_placeholder.container():
            # Wir versehen den Bereich rund um den Start-Button mit einem individuellen CSS-Block,
            # sodass das "OK"-Element deutlich hervorgehoben wird. Solange auf dieser Seite nur
            # dieser Button verwendet wird, wirkt sich das Styling ausschließlich auf ihn aus.
            # Das CSS wird bei jedem Rerun neu angefügt, was in Streamlit unproblematisch ist und
            # sicherstellt, dass das Styling nach einem Reload zuverlässig greift.
            st.markdown(
                """
                <style>
                    /*
                     * Die Klasse ``stButton`` kapselt den gerenderten Button. Über die direkte
                     * Selektoransprache steuern wir gezielt das Aussehen des hier benötigten
                     * Elements, ohne zusätzliche Bibliotheken zu laden. Falls weitere Buttons
                     * hinzukommen, kann das Styling bei Bedarf durch eine spezifischere Klasse
                     * ergänzt werden.
                     */
                    div[data-testid="stButton"] {
                        margin-top: 1.5rem;
                        display: flex;
                        justify-content: center;
                    }
                    div[data-testid="stButton"] > button {
                        background-color: #2e7d32;
                        border: 2px solid #1b5e20;
                        color: #ffffff;
                        font-weight: 700;
                        padding: 0.75rem 2.5rem;
                        border-radius: 999px;
                        box-shadow: 0 0 0 1px rgba(27, 94, 32, 0.35);
                    }
                    div[data-testid="stButton"] > button:hover {
                        background-color: #1b5e20;
                        border-color: #174f1b;
                    }
                    div[data-testid="stButton"] > button:focus {
                        outline: 3px solid rgba(56, 142, 60, 0.45);
                        outline-offset: 2px;
                    }
                </style>
                """,
                unsafe_allow_html=True,
            )

            # Durch die Nutzung von ``st.button`` behalten wir die vertraute Streamlit-Interaktion
            # bei und können den Button im Anschluss eindeutig verarbeiten. Sollte das Styling
            # debuggt werden müssen, lässt sich der CSS-Block oben temporär auskommentieren.
            button_gedrueckt = st.button("OK", key="start_ok_button", type="primary")

            if button_gedrueckt:
                # Der Seitenwechsel erfolgt über ``st.switch_page``. Dies stellt sicher, dass der
                # Multipage-Mechanismus von Streamlit genutzt wird und die Session-States erhalten
                # bleiben. Bei Bedarf kann hier für Debug-Zwecke eine zusätzliche ``st.write``-
                # Ausgabe aktiviert werden, um den Seitenwechsel zu protokollieren.
                st.switch_page("pages/1_Anamnese.py")

    st.stop()

