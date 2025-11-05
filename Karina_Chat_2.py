"""Startseite der virtuellen Sprechstunde.

Dieses Skript dient ausschließlich als Einstiegspunkt in die Multipage-Anwendung.
Es zeigt das Szenario-Auswahlverfahren und die Instruktionen an, bevor automatisch
auf die einzelnen Seiten (Anamnese, Untersuchung, Diagnostik usw.) verzweigt wird.
"""

import os

import streamlit as st
from openai import OpenAI

# Externe Helfermodule, die für die Fallvorbereitung und das Startlayout benötigt werden.
from module.sidebar import show_sidebar
from module.startinfo import zeige_instruktionen_vor_start
from module.offline import display_offline_banner
from module.fallverwaltung import (
    fallauswahl_prompt,
    lade_fallbeispiele,
    prepare_fall_session_state,
)
from module.fall_config import clear_fixed_scenario, get_fall_fix_state
from module.feedback_mode import determine_feedback_mode
from module.footer import copyright_footer

# ---------------------------------------------------------------------------
# Initialisierung
# ---------------------------------------------------------------------------

# Einmaliger Aufbau des OpenAI-Clients. Die nachfolgenden Seiten greifen über den
# Session-State darauf zu, weshalb wir die Instanz hier zentral ablegen.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
st.session_state["openai_client"] = client


def initialisiere_session_state() -> None:
    """Hinterlegt Basiswerte im ``st.session_state`` für einen sauberen Neustart."""

    # Für alle Module sollen nachvollziehbare Standardwerte existieren. Durch die
    # Verwendung von ``setdefault`` bleiben bereits gesetzte Werte (z. B. beim
    # erneuten Laden der Startseite) unverändert.
    st.session_state.setdefault("final_feedback", "")
    st.session_state.setdefault("final_diagnose", "")
    st.session_state.setdefault("offline_mode", False)
    st.session_state.setdefault("fall_vorbereitung_abgeschlossen", False)


initialisiere_session_state()
# Der Feedback-Modus wird direkt bestimmt, damit Admin-Vorgaben auf allen Seiten
# konsistent sichtbar sind. Eventuelle Debug-Hilfen lassen sich in
# ``module.feedback_mode`` aktivieren.
determine_feedback_mode()


# ---------------------------------------------------------------------------
# Vorbereitung des Falls
# ---------------------------------------------------------------------------

def fuehre_fall_vorbereitung_durch() -> None:
    """Bereitet das gewählte Fallszenario vollständig vor."""

    if st.session_state.get("fall_vorbereitung_abgeschlossen", False):
        return  # Die Vorbereitung läuft nur einmal pro Sitzung.

    st.markdown("#### ⏳ Vorbereitung des Falls")

    # Die Falldaten werden erst geladen, sobald die Instruktionen angezeigt
    # werden. Dadurch bleibt der erste Eindruck aufgeräumt und es entsteht kein
    # fühlbarer Verzug zwischen Hinweistext und Ladeindikator.
    szenario_df = st.session_state.get("fallliste_df")
    if szenario_df is None:
        szenario_df = lade_fallbeispiele()
        st.session_state["fallliste_df"] = szenario_df

    if szenario_df.empty:
        st.error(
            "❌ Die Fallliste konnte nicht geladen werden. Bitte Datenquelle oder Netzwerk prüfen."
        )
        st.session_state.fall_vorbereitung_abgeschlossen = True
        return

    # Priorität haben Admin-Vorgaben, danach folgen fest eingestellte Szenarien.
    fixed, fixed_szenario = get_fall_fix_state()
    admin_szenario = st.session_state.pop("admin_selected_szenario", None)
    if admin_szenario:
        fallauswahl_prompt(szenario_df, admin_szenario)
    elif fixed and fixed_szenario:
        if "Szenario" in szenario_df.columns:
            verfuegbare_szenarien = {
                str(s).strip() for s in szenario_df["Szenario"].dropna() if str(s).strip()
            }
        else:
            verfuegbare_szenarien = set()

        if fixed_szenario in verfuegbare_szenarien:
            fallauswahl_prompt(szenario_df, fixed_szenario)
        else:
            st.warning(
                f"Das fixierte Szenario '{fixed_szenario}' ist nicht mehr verfügbar. Die Fixierung wurde aufgehoben."
            )
            clear_fixed_scenario()
            fallauswahl_prompt(szenario_df)
    elif "diagnose_szenario" not in st.session_state:
        # Falls keine Vorgaben existieren, zieht die Anwendung ein zufälliges Szenario.
        fallauswahl_prompt(szenario_df)

    # Nach der Auswahl werden sämtliche Patient:innendaten vorbereitet. Auf diese
    # Werte greifen die Unterseiten unmittelbar zu. Für Debugging kann hier
    # temporär ``st.write(st.session_state)`` aktiviert werden.
    prepare_fall_session_state()

    patient_name = st.session_state.get("patient_name", "").strip()
    if patient_name:
        start_hinweis = f"✅ Fallvorbereitung abgeschlossen. Beginnen Sie das Gespräch mit {patient_name}."
    else:
        start_hinweis = (
            "✅ Fallvorbereitung abgeschlossen. Beginnen Sie das Gespräch mit der simulierten Patientin oder dem Patienten."
        )
    st.success(start_hinweis)

    st.session_state.fall_vorbereitung_abgeschlossen = True


# ---------------------------------------------------------------------------
# Layout der Startseite
# ---------------------------------------------------------------------------

show_sidebar()
display_offline_banner()

# Ein prägnanter Titel erleichtert die Orientierung. Alle weiterführenden
# Hinweise liefert der Instruktionsdialog.
st.title("Virtuelle Sprechstunde")

# ``zeige_instruktionen_vor_start`` blendet den erklärenden Dialog ein, führt die
# Fallvorbereitung aus und leitet anschließend automatisch zur Anamnese weiter.
zeige_instruktionen_vor_start(lade_callback=fuehre_fall_vorbereitung_durch)

# Hinweis für künftige Erweiterungen: Die obige Funktion ruft ``st.stop()`` auf.
# Code unterhalb dieser Zeilen wird daher nicht ausgeführt. Für Debugging kann
# die Stop-Anweisung im Modul vorübergehend deaktiviert werden.
copyright_footer()
