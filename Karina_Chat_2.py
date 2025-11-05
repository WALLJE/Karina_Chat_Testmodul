

import streamlit as st
from openai import OpenAI
import os
from datetime import datetime

# externe Codes einbinden
from diagnostikmodul import diagnostik_und_befunde_routine
from feedbackmodul import feedback_erzeugen
from sprachmodul import sprach_check
from module.untersuchungsmodul import generiere_koerperbefund
from befundmodul import generiere_befund
from module.sidebar import show_sidebar
from module.startinfo import zeige_instruktionen_vor_start
from module.token_counter import init_token_counters, add_usage
from module.offline import display_offline_banner, is_offline
from module.gpt_feedback import (
    speichere_gpt_feedback_in_supabase as speichere_feedback_mit_modus,
)
from module.loading_indicator import task_spinner
from module.fallverwaltung import (
    fallauswahl_prompt,
    lade_fallbeispiele,
    prepare_fall_session_state,
)
from module.fall_config import clear_fixed_scenario, get_fall_fix_state
from module.feedback_mode import determine_feedback_mode
from module.footer import copyright_footer

# Open AI API-Key setzen
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
st.session_state["openai_client"] = client

# Zugriff via Streamlit Secrets
# nextcloud_url = st.secrets["nextcloud"]["url"]
# nextcloud_user = st.secrets["nextcloud"]["user"]
# nextcloud_token = st.secrets["nextcloud"]["token"]
# auth = HTTPBasicAuth(nextcloud_user, nextcloud_token)

# st.set_page_config(layout="wide") # breiter Bildschrim sieht nicht gut aus.

def initialisiere_session_state():
    st.session_state.setdefault("final_feedback", "") #test
    st.session_state.setdefault("feedback_prompt_final", "") #test
    st.session_state.setdefault("final_diagnose", "") #test
    st.session_state.setdefault("offline_mode", False)
    st.session_state.setdefault("koerper_befund_generating", False)
    st.session_state.setdefault("befund_generating", False)
    st.session_state.setdefault("befund_generierung_gescheitert", False)
    st.session_state.setdefault("fall_vorbereitung_abgeschlossen", False)


def aktualisiere_kumulative_befunde(neuer_befund: str) -> None:
    """Sichert den jüngsten Befund sowie eine kumulierte Übersicht im ``session_state``."""

    # Der Primärbefund wird für die direkte Anzeige gespeichert.
    st.session_state["befunde"] = neuer_befund

    # Vorbereitung der kumulativen Darstellung aller Termine.
    kumulative_passagen = [f"### Termin 1\n{neuer_befund}".strip()]
    gesamt = st.session_state.get("diagnostik_runden_gesamt", 1)
    for termin in range(2, gesamt + 1):
        befund_key = f"befunde_runde_{termin}"
        gespeicherter_befund = st.session_state.get(befund_key, "").strip()
        if gespeicherter_befund:
            kumulative_passagen.append(f"### Termin {termin}\n{gespeicherter_befund}")

    # Ablage der Texte für Feedback- und Exportfunktionen.
    kumuliert = "\n---\n".join(kumulative_passagen).strip()
    st.session_state["gpt_befunde"] = neuer_befund
    st.session_state["gpt_befunde_kumuliert"] = kumuliert


def starte_automatische_befundgenerierung() -> None:
    """Löst ohne zusätzlichen Klick die Befundgenerierung aus, sobald alle Eingaben vorliegen."""

    if st.session_state.get("befund_generating", False):
        return  # Eine laufende Generierung wird nicht erneut angestoßen.
    if st.session_state.get("befunde"):
        return  # Bereits vorhandene Befunde müssen nicht erneut erzeugt werden.
    if st.session_state.get("befund_generierung_gescheitert", False):
        return  # Bei Fehlern wird der Fallback-Button sichtbar, automatische Versuche pausieren.

    diagnostik_text = st.session_state.get("user_diagnostics", "").strip()
    ddx_text = st.session_state.get("user_ddx2", "").strip()
    if not diagnostik_text or not ddx_text:
        return  # Ohne vollständige Eingaben ist kein zielführender Befund möglich.

    st.session_state["befund_generating"] = True
    st.session_state.pop("befund_generierungsfehler", None)

    try:
        diagnose_szenario = st.session_state.get("diagnose_szenario", "")
        if is_offline():
            befund = generiere_befund(client, diagnose_szenario, diagnostik_text)
            aktualisiere_kumulative_befunde(befund)
        else:
            ladeaufgaben = [
                "Lade Falldaten aus dem aktuellen Szenario",
                "Analysiere diagnostische Eingaben",
                "Formuliere strukturierten Befund",
            ]
            with task_spinner("Befunde werden automatisch generiert...", ladeaufgaben) as indikator:
                indikator.advance(1)
                befund = generiere_befund(client, diagnose_szenario, diagnostik_text)
                indikator.advance(1)
                aktualisiere_kumulative_befunde(befund)
                indikator.advance(1)
    except Exception as error:
        # Für gezielte Fehlersuche wird der Hinweis gespeichert und der Fallback-Button freigegeben.
        st.session_state["befund_generierung_gescheitert"] = True
        st.session_state["befund_generierungsfehler"] = str(error)
    else:
        st.session_state["befund_generierung_gescheitert"] = False
    finally:
        st.session_state["befund_generating"] = False

    if not st.session_state.get("befund_generierung_gescheitert", False):
        st.rerun()


def generiere_koerperbefund_interaktiv(client: OpenAI) -> None:
    """Erstellt den körperlichen Befund einheitlich für Autostart und Button-Klick."""

    # Sofortiger Abbruch, falls bereits eine Generierung läuft – damit vermeiden wir doppelte API-Aufrufe.
    if st.session_state.get("koerper_befund_generating", False):
        return

    st.session_state.koerper_befund_generating = True

    # Alle notwendigen Eingaben werden zentral zusammengestellt, damit der eigentliche Generierungscode übersichtlich bleibt.
    diagnose_szenario = st.session_state.get("diagnose_szenario", "")
    diagnose_features = st.session_state.get("diagnose_features")
    koerper_befund_tip = st.session_state.get("koerper_befund_tip")
    patient_name = st.session_state.get("patient_name", "Der Patient / die Patientin")

    try:
        if is_offline():
            # Offline greifen wir direkt auf die lokale Hilfsfunktion zu – ideal für Workshops ohne Internet.
            koerper_befund = generiere_koerperbefund(
                client,
                diagnose_szenario,
                diagnose_features,
                koerper_befund_tip,
            )
            st.session_state.koerper_befund = koerper_befund
            st.info(
                "🔌 Offline-Befund geladen. Sobald der Online-Modus aktiv ist, kannst du einen KI-generierten Befund abrufen."
            )
        else:
            untersuchungsaufgaben = [
                "Sammle anamnestische Schlüsselhinweise",
                "Berechne passende Untersuchungsbefunde",
                "Bereite Ergebnistext für die Anzeige auf",
            ]
            # Der Spinner sorgt für nachvollziehbares Feedback – das stärkt das Vertrauen während der Verarbeitung.
            with task_spinner(
                f"{patient_name} wird untersucht...",
                untersuchungsaufgaben,
            ) as indikator:
                indikator.advance(1)
                koerper_befund = generiere_koerperbefund(
                    client,
                    diagnose_szenario,
                    diagnose_features,
                    koerper_befund_tip,
                )
                indikator.advance(1)
                st.session_state.koerper_befund = koerper_befund
                indikator.advance(1)

        st.session_state.koerper_befund_generating = False

        # Debug-Hinweis: Bei Bedarf st.write("Befund:", st.session_state.koerper_befund) aktivieren, um Antworten zu prüfen.
        st.rerun()

    except RateLimitError:
        st.session_state.koerper_befund_generating = False
        st.error("🚫 Die Untersuchung konnte nicht erstellt werden. Die OpenAI-API ist derzeit überlastet.")

    except Exception as err:
        st.session_state.koerper_befund_generating = False
        st.error(f"❌ Unerwarteter Fehler bei der Untersuchung: {err}")
        # Debug-Tipp: Mit st.exception(err) lassen sich ausführliche Tracebacks anzeigen, falls nötig.

def speichere_gpt_feedback_in_supabase():
    """Leitet die Supabase-Speicherung an das neue Hilfsmodul weiter."""

    # Die bisherige Implementierung wurde hier bewusst ersetzt, damit exakt dieselbe
    # Logik genutzt wird wie auf der dedizierten Feedback-Seite (``pages/6_Feedback.py``).
    # Dort wird der Feedback-Modus ("Client") bereits berücksichtigt und zuverlässig in
    # Supabase abgelegt. Durch die Bündelung vermeiden wir divergierende Datenstrukturen.
    speichere_feedback_mit_modus()

#---------------- Routinen Ende -------------------
initialisiere_session_state()
# Der Feedback-Modus wird gleich beim Start festgelegt, damit der Adminbereich
# unmittelbar eine aussagekräftige Statusmeldung anzeigen kann. Die Funktion
# berücksichtigt bestehende Übersteuerungen und persistierte Einstellungen.
determine_feedback_mode()

#####
# Testlauf
# diagnostik_und_befunde_routine(client)
# diagnostik_eingaben, gpt_befunde = diagnostik_und_befunde_routine(client, start_runde=2)
# anzahl_runden = st.session_state.get("diagnostik_runden_gesamt", 1)
# st.write ("Status:", diagnostik_eingaben, gpt_befunde, anzahl_runden)
#####

def fuehre_fall_vorbereitung_durch() -> None:
    """Bereitet das ausgewählte Fallszenario vollständig vor."""

    # Sobald die Fallvorbereitung abgeschlossen wurde, wird sie nicht erneut gestartet.
    if st.session_state.get("fall_vorbereitung_abgeschlossen", False):
        return

    # Der Ladeabschnitt wird direkt unterhalb der Instruktionen eingeblendet. Damit entsteht
    # keine wahrnehmbare Verzögerung zwischen dem Lesen der Hinweise und dem eigentlichen
    # Vorbereiten des Falls.
    st.markdown("#### ⏳ Vorbereitung des Falls")

    # Wir laden die Falldaten erst an dieser Stelle, damit garantiert die Instruktionen als
    # erster Bildschirm erscheinen. Für wiederholte Aufrufe halten wir den DataFrame im
    # Session State vor; so vermeiden wir unnötige Netzwerkanfragen während einer Sitzung.
    szenario_df = st.session_state.get("fallliste_df")
    if szenario_df is None:
        szenario_df = lade_fallbeispiele()
        st.session_state["fallliste_df"] = szenario_df

    if szenario_df.empty:
        # Ohne Datengrundlage informieren wir klar über das Problem.
        st.error(
            "❌ Die Fallliste konnte nicht geladen werden. Bitte prüfen Sie die Datenquelle oder die Netzwerkverbindung."
        )
        st.session_state.fall_vorbereitung_abgeschlossen = True
        return

    # Informationen zu einer eventuellen Fall-Fixierung werden jedes Mal frisch abgefragt,
    # damit Änderungen an der Konfiguration sofort greifen.
    fixed, fixed_szenario = get_fall_fix_state()

    # Admin-Vorgaben besitzen höchste Priorität und überschreiben Zufallsauswahl oder Fixierung.
    admin_szenario = st.session_state.pop("admin_selected_szenario", None)
    if admin_szenario:
        fallauswahl_prompt(szenario_df, admin_szenario)
    elif fixed and fixed_szenario:
        # Bei fixierten Fällen stellen wir sicher, dass das Szenario weiterhin in der Liste existiert.
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
        # Wenn noch kein Fall gewählt wurde, greifen wir auf die Zufallsauswahl zurück.
        fallauswahl_prompt(szenario_df)

    # Sobald das Szenario ausgewählt ist, werden alle weiteren Patient*innen-Daten
    # unmittelbar vorbereitet. Dadurch stehen Name, Alter, Bildhinweise usw. bereits
    # zur Verfügung, während die Instruktionen noch sichtbar sind.
    prepare_fall_session_state()

    # Für Entwicklerinnen und Entwickler ist es hilfreich zu wissen, dass an dieser Stelle
    # ein vollständiger Satz an Session-State-Werten vorliegt. Bei Bedarf kann hier eine
    # Debug-Ausgabe (z. B. ``st.write(st.session_state)``) aktiviert werden.

    # Nachdem alle Patient:innendaten geladen wurden, greifen wir auf den Namen zu und
    # führen die Studierenden direkt ins Gespräch. Sollte der Name unerwartet fehlen,
    # informieren wir weiterhin neutral – so erkennt man sofort, wo ein Debugging ansetzen
    # müsste (z. B. durch eine temporäre ``st.write``-Ausgabe unmittelbar vor dieser Stelle).
    patient_name = st.session_state.get("patient_name", "").strip()
    if patient_name:
        start_hinweis = f"✅ Fallvorbereitung abgeschlossen. Beginnen Sie das Gespräch mit {patient_name}."
    else:
        start_hinweis = (
            "✅ Fallvorbereitung abgeschlossen. Beginnen Sie das Gespräch mit der simulierten Patientin oder dem Patienten."
        )
    st.success(start_hinweis)

    # Status-Flag setzen, damit spätere Aufrufe übersprungen werden.
    st.session_state.fall_vorbereitung_abgeschlossen = True


zeige_instruktionen_vor_start(lade_callback=fuehre_fall_vorbereitung_durch)

# Die nachfolgenden Schritte werden erst ausgeführt, wenn die Instruktionen bestätigt wurden
# und der Nutzer bzw. die Nutzerin sich in die eigentliche Sprechstunde begibt.
if st.session_state.get("diagnose_szenario"):
    prepare_fall_session_state()

show_sidebar()

display_offline_banner()

st.title("Virtuelle Sprechstunde")
st.markdown("<br>", unsafe_allow_html=True)

# Startzeit einfügen
if "startzeit" not in st.session_state:
    st.session_state.startzeit = datetime.now()

# zur STeuerung der Diagnostik Abfragen zurücksetzten
st.session_state.setdefault("diagnostik_aktiv", False)


####### Debug
#st.write("Szenario:", st.session_state.diagnose_szenario)
#st.write("Features:", st.session_state.diagnose_features)
#st.write("Prompt:", st.session_state.SYSTEM_PROMPT)
#speichere_gpt_feedback_in_supabase()


# Chat-Verlauf starten
# with col1: # nur links
if "messages" not in st.session_state:
    eintritt = (
        f"ist {st.session_state.patient_age} Jahre alt, arbeitet als {st.session_state.patient_job} "
        "und betritt den Raum."
    )
    if "ängstlich" in st.session_state.patient_verhalten.lower():
        start_text = "Hallo... ich bin etwas nervös. Ich hoffe, Sie können mir helfen."
    elif "redest gern" in st.session_state.patient_verhalten.lower():
        start_text = "Hallo! Schön, dass ich hier bin – ich erzähle Ihnen gern, was bei mir los ist."
    else:
        start_text = "Guten Tag, ich bin froh, dass ich mich heute bei Ihnen vorstellen kann."
    st.session_state.messages = [
        {"role": "system", "content": st.session_state.SYSTEM_PROMPT},
        {"role": "assistant", "content": eintritt},
        {"role": "assistant", "content": start_text}
    ]

# Chat anzeigen
for msg in st.session_state.messages[1:]:
    sender = st.session_state.patient_name if msg["role"] == "assistant" else "Du"
    st.markdown(f"**{sender}:** {msg['content']}")

# Eingabeformular Anamnese Chat
with st.form(key="eingabe_formular", clear_on_submit=True):
    user_input = st.text_input(f"Deine Frage an {st.session_state.patient_name}:")
    submit_button = st.form_submit_button(label="Absenden")

if submit_button and user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    dialog_aufgaben = [
        "Übermittle Frage an das Sprachmodell",
        "Warte auf Antwortgenerierung",
        "Bereite Ausgabe für den Chat vor",
    ]
    with task_spinner(f"{st.session_state.patient_name} antwortet...", dialog_aufgaben) as indikator:
        try:
            init_token_counters()
            indikator.advance(1)
            response = client.chat.completions.create(
                model="gpt-4",
                messages=st.session_state.messages,
                temperature=0.6
            )
            indikator.advance(1)
            add_usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
            reply = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": reply})
            indikator.advance(1)
        except RateLimitError:
            st.error("🚫 Die Anfrage konnte nicht verarbeitet werden, da die OpenAI-API derzeit überlastet ist. Bitte versuchen Sie es in einigen Minuten erneut.")
    st.rerun()


# Abschnitt: Körperliche Untersuchung
st.markdown("---")
anzahl_fragen = sum(1 for m in st.session_state.messages if m["role"] == "user")

if anzahl_fragen > 0:
    st.subheader("Körperliche Untersuchung")

    if (
        not st.session_state.get("koerper_befund")
        and not st.session_state.get("koerper_befund_generating", False)
    ):
        generiere_koerperbefund_interaktiv(client)
        # Debug-Hinweis: Bei Bedarf kann hier ein st.write(...) aktiviert werden, um Details zur Generierung anzuzeigen.

#Debug
    # st.write("Szenario:", st.session_state.diagnose_szenario)
    # st.write("Features:", st.session_state.diagnose_features)
    # st.write("Prompt:", st.session_state.SYSTEM_PROMPT)
    if "koerper_befund" in st.session_state:
        st.success("✅ Körperliche Untersuchung erfolgt.")
        st.markdown(st.session_state.koerper_befund)
    else:
        if st.button(
            "Untersuchung durchführen",
            disabled=st.session_state.get("koerper_befund_generating", False),
        ):
            generiere_koerperbefund_interaktiv(client)

else:
    st.subheader("Körperliche Untersuchung")
    st.button("Untersuchung durchführen", disabled=True)
    st.info("❗Bitte stellen Sie zunächst mindestens eine anamnestische Frage.")

# Abschnitt: Differentialdiagnosen und diagnostische Maßnahmen
st.markdown("---")
if "koerper_befund" in st.session_state:
    st.subheader("Differentialdiagnosen und diagnostische Maßnahmen")

    if "user_ddx2" not in st.session_state:
        with st.form("differentialdiagnosen_diagnostik_formular"):
            ddx_input2 = st.text_area("Welche drei Differentialdiagnosen halten Sie nach Anamnese und Untersuchung für möglich?", key="ddx_input2")
            diag_input2 = st.text_area("Welche konkreten diagnostischen Maßnahmen möchten Sie vorschlagen?", key="diag_input2")
            submitted_diag = st.form_submit_button("✅ Eingaben speichern")

        if submitted_diag:
            st.session_state.user_ddx2 = sprach_check(ddx_input2, client)
            st.session_state.user_diagnostics = sprach_check(diag_input2, client)
            # Nach dem Sichern der Eingaben wird der automatische Befundlauf gestartet.
            starte_automatische_befundgenerierung()

    else:
        # st.markdown("📝 **Ihre gespeicherten Eingaben:**")
        st.markdown(f"**Differentialdiagnosen:**  \n{st.session_state.user_ddx2}")
        st.markdown(f"**Diagnostische Maßnahmen:**  \n{st.session_state.user_diagnostics}")

    starte_automatische_befundgenerierung()

else:
    st.subheader("Differentialdiagnosen und diagnostische Maßnahmen")
    st.info("❗Bitte führen Sie zuerst die körperliche Untersuchung durch.")


# Abschnitt: Ergebnisse der diagnostischen Maßnahmen
st.markdown("---")

if (
    "koerper_befund" in st.session_state
    and "user_diagnostics" in st.session_state
    and "user_ddx2" in st.session_state
):
    st.subheader("📄 Befunde")

    if "befunde" in st.session_state:
        # st.success("✅ Befunde wurden erstellt.")
        st.markdown(st.session_state.befunde)
        if st.session_state.get("befund_generierungsfehler"):
            st.info(
                "ℹ️ Der automatische Lauf meldete zuvor einen Fehler. Durch den gespeicherten Befund wurde der Hinweis"
                " für Transparenz belassen."
            )
    else:
        # Falls gewünscht, kann hier zur Fehlersuche eine Debug-Ausgabe aktiviert werden.
        if st.session_state.get("befund_generierungsfehler"):
            st.error(
                "❌ Automatische Befundgenerierung fehlgeschlagen: "
                f"{st.session_state['befund_generierungsfehler']}"
            )
        if st.session_state.get("befund_generierung_gescheitert", False):
            if st.button("🧪 Befunde generieren lassen"):
                try:
                    st.session_state["befund_generating"] = True
                    diagnostik_eingabe = st.session_state.user_diagnostics
                    diagnose_szenario = st.session_state.diagnose_szenario

                    if is_offline():
                        befund = generiere_befund(client, diagnose_szenario, diagnostik_eingabe)
                        aktualisiere_kumulative_befunde(befund)
                    else:
                        ladeaufgaben = [
                            "Bereite diagnostische Eingaben auf",
                            "Rekontextualisiere Fallinformationen",
                            "Formuliere aktualisierten Befund",
                        ]
                        with task_spinner("Befunde werden erneut generiert...", ladeaufgaben) as indikator:
                            indikator.advance(1)
                            befund = generiere_befund(client, diagnose_szenario, diagnostik_eingabe)
                            indikator.advance(1)
                            aktualisiere_kumulative_befunde(befund)
                            indikator.advance(1)
                    st.session_state["befund_generierung_gescheitert"] = False
                    st.session_state.pop("befund_generierungsfehler", None)
                    st.session_state["befund_generating"] = False
                    st.rerun()

                except Exception as error:
                    st.session_state["befund_generating"] = False
                    st.error(f"❌ Manueller Fallback fehlgeschlagen: {error}")
                    # Hinweis: Für tiefergehendes Debugging können hier zusätzliche Logs ergänzt werden.

else:
    st.subheader("📄 Befunde")
    st.button("🧪 Befunde generieren lassen", disabled=True)
    st.info("❗Bitte führen Sie zuerst die körperliche Untersuchung durch.")


# Weitere Diagnostik-Termine 
if not st.session_state.get("final_diagnose", "").strip():
    if (
        "diagnostik_eingaben" not in st.session_state
        or "gpt_befunde" not in st.session_state
        or st.session_state.get("diagnostik_aktiv", False)
    ):
        diagnostik_eingaben, gpt_befunde = diagnostik_und_befunde_routine(
            client,
            start_runde=2,
            weitere_diagnostik_aktiv=False  # wichtig!
        )
        st.session_state["diagnostik_eingaben"] = diagnostik_eingaben
        st.session_state["gpt_befunde"] = gpt_befunde
    else:
        diagnostik_eingaben = st.session_state["diagnostik_eingaben"]
        gpt_befunde = st.session_state["gpt_befunde"]

    # Ausgabe der bisherigen Befunde
    gesamt = st.session_state.get("diagnostik_runden_gesamt", 1)
    for i in range(2, gesamt + 1):
        bef_key = f"befunde_runde_{i}"
        bef = st.session_state.get(bef_key, "")
        if bef:
            st.markdown(f"📅 Termin {i}")
            st.markdown(bef)

# Anzeige für neuen Termin (nur nach Button)
gesamt = st.session_state.get("diagnostik_runden_gesamt", 1)
neuer_termin = gesamt + 1

if (
    st.session_state.get("diagnostik_aktiv", False)
    and f"diagnostik_runde_{neuer_termin}" not in st.session_state
):
    st.markdown(f"### 📅 Termin {neuer_termin}")
    with st.form(key=f"diagnostik_formular_runde_{neuer_termin}_hauptskript"):
        neue_diagnostik = st.text_area(
            "Welche zusätzlichen diagnostischen Maßnahmen möchten Sie anfordern?",
            key=f"eingabe_diag_r{neuer_termin}"
        )
        submitted = st.form_submit_button("✅ Diagnostik anfordern")

    if submitted and neue_diagnostik.strip():
        neue_diagnostik = neue_diagnostik.strip()
        st.session_state[f"diagnostik_runde_{neuer_termin}"] = neue_diagnostik

        szenario = st.session_state.get("diagnose_szenario", "")
        ladeaufgaben = [
            "Übertrage neue Diagnostik an das Modell",
            "Vergleiche Eingaben mit bisherigen Befunden",
            "Generiere aktualisierte Rückmeldung",
        ]
        with task_spinner("GPT erstellt Befunde...", ladeaufgaben) as indikator:
            indikator.advance(1)
            befund = generiere_befund(client, szenario, neue_diagnostik)
            indikator.advance(1)
            st.session_state[f"befunde_runde_{neuer_termin}"] = befund
            indikator.advance(1)
            st.session_state["diagnostik_runden_gesamt"] = neuer_termin
            st.session_state["diagnostik_aktiv"] = False
            st.rerun()
    
    # 🔄 Button wieder anzeigen, wenn kein Formular aktiv ist
    if (
        not st.session_state.get("diagnostik_aktiv", False)
        and ("befunde" in st.session_state or gesamt >= 2)
    ):
        if st.button("➕ Weitere Diagnostik anfordern", key="btn_neue_diagnostik"):
            st.session_state["diagnostik_aktiv"] = True
            st.rerun()


# Diagnose und Therapie
if "befunde" in st.session_state:
    st.markdown("### Diagnose und Therapiekonzept")
    if st.session_state.final_diagnose.strip() and st.session_state.therapie_vorschlag.strip():
        st.markdown(f"**Ihre Diagnose:**  \n{st.session_state.final_diagnose}")
        st.markdown(f"**Therapiekonzept:**  \n{st.session_state.therapie_vorschlag}")
    else:
        with st.form("diagnose_therapie"):
            input_diag = st.text_input("Ihre endgültige Diagnose:")
            input_therapie = st.text_area("Ihr Therapiekonzept, bitte ggf. ausführlicher beschreiben:")
            submitted_final = st.form_submit_button("✅ Senden")

        if submitted_final:
            st.session_state.final_diagnose = sprach_check(input_diag, client)
            st.session_state.therapie_vorschlag = sprach_check(input_therapie, client)
            # st.success("✅ Entscheidung gespeichert")
            st.rerun()

# Abschlussfeedback
st.markdown("---")
st.subheader("📋 Feedback durch KI")

diagnose_eingegeben = st.session_state.get("final_diagnose", "").strip() != ""
therapie_eingegeben = st.session_state.get("therapie_vorschlag", "").strip() != ""

if diagnose_eingegeben and therapie_eingegeben:
    if st.session_state.get("final_feedback", "").strip():
        # Feedback wurde schon erzeugt
        # st.success("✅ Feedback erstellt.")
        # st.markdown("### Strukturierte Rückmeldung zur Fallbearbeitung:")
        st.markdown(st.session_state.final_feedback)
    else:
        if st.button("📋 Abschluss-Feedback anzeigen"):
            # Rückfall auf gespeicherte Diagnostik-Eingaben, falls nötig
            diagnostik_eingaben = st.session_state.get("diagnostik_eingaben", "Keine weiteren diagnostischen Maßnahmen gespeichert.")
            gpt_befunde = st.session_state.get("gpt_befunde", "")
            # Fallback: Termin 1 verwenden, wenn keine späteren diagnostik_eingaben gespeichert sind
            if not diagnostik_eingaben.strip() and not gpt_befunde.strip():
                diagnostik_eingaben = f"### Termin 1\n{st.session_state.get('user_diagnostics', 'Keine Angabe')}"
                gpt_befunde = f"### Termin 1\n{st.session_state.get('befunde', 'Kein Befund erzeugt')}"


            anzahl_termine = st.session_state.get("diagnostik_runden_gesamt", 1)
            # Variablen sammeln
            user_ddx2 = st.session_state.get("user_ddx2", "Keine Differentialdiagnosen angegeben.")
            # user_diagnostics = st.session_state.get("user_diagnostics", "Keine diagnostischen Maßnahmen angegeben.")
            # befunde = st.session_state.get("befunde", "Keine Befunde generiert.")
            koerper_befund = st.session_state.get("koerper_befund", "Keine Körperliche Untersuchung generiert")
            final_diagnose = st.session_state.get("final_diagnose", "Keine finale Diagnose eingegeben.")
            therapie_vorschlag = st.session_state.get("therapie_vorschlag", "Kein Therapiekonzept eingegeben.")
            diagnose_szenario=st.session_state.get("diagnose_szenario", "")
            user_verlauf = "\n".join([
                msg["content"] for msg in st.session_state.messages
                if msg["role"] == "user"
            ])
            
            #DEBUG
            st.write("DEBUG: diagnostik_eingaben =", diagnostik_eingaben)
          
            feedback = feedback_erzeugen(
                client,
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
            speichere_gpt_feedback_in_supabase()
            st.success("✅ Evaluation erstellt")
            st.rerun()
else:
    st.button("📋 Abschluss-Feedback anzeigen", disabled=True)
    st.info("❗Bitte tragen Sie eine finale Diagnose und ein Therapiekonzept ein.")
    

# Downloadbereich
# Zusammenfassung und Download vorbereiten
st.markdown("---")
st.subheader("📄 Download")

if "final_feedback" in st.session_state:
    protokoll = ""

    # Szenario
    protokoll += f"Simuliertes Krankheitsbild: {st.session_state.diagnose_szenario}\n\n"

    # Gesprächsverlauf
    protokoll += "---\n💬 Gesprächsverlauf (nur Fragen des Studierenden):\n"
    for msg in st.session_state.messages[1:]:
        rolle = st.session_state.patient_name if msg["role"] == "assistant" else "Du"
        protokoll += f"{rolle}: {msg['content']}\n"

    # Körperlicher Untersuchungsbefund
    if "koerper_befund" in st.session_state:
        protokoll += "\n---\nKörperlicher Untersuchungsbefund:\n"
        protokoll += st.session_state.koerper_befund + "\n"

    # Differentialdiagnosen
    if "user_ddx2" in st.session_state:
        protokoll += "\n---\nErhobene Differentialdiagnosen:\n"
        protokoll += st.session_state.user_ddx2 + "\n"

    # Diagnostische Maßnahmen
    if "user_diagnostics" in st.session_state:
        protokoll += "\n---\n🔬 Geplante diagnostische Maßnahmen:\n"
        protokoll += st.session_state.user_diagnostics + "\n"

    # Generierte Befunde
    if "befunde" in st.session_state:
        protokoll += "\n---\n📄 Ergebnisse der diagnostischen Maßnahmen:\n"
        protokoll += st.session_state.befunde + "\n"

    # Finale Diagnose
    if "final_diagnose" in st.session_state:
        protokoll += "\n---\nFinale Diagnose:\n"
        protokoll += st.session_state.final_diagnose + "\n"

    # Therapiekonzept
    if "therapie_vorschlag" in st.session_state:
        protokoll += "\n---\n Therapiekonzept:\n"
        protokoll += st.session_state.therapie_vorschlag + "\n"

    # Abschlussfeedback
    protokoll += "\n---\n Strukturierte Rückmeldung:\n"
    protokoll += st.session_state.final_feedback + "\n"

    # Download-Button
    st.download_button(
        label="⬇️ Gespräch & Feedback herunterladen",
        data=protokoll,
        file_name="karina_chatprotokoll.txt",
        mime="text/plain"
    )
else:
    st.info("💬 Das Protokoll kann nach der Evaluation heruntergeladen werden.")

copyright_footer()
