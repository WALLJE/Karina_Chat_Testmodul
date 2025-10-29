# Version 18
#  
# Features:
# Feedback in Supabase gespeichert
# Einweisung Studierende mit Stopfunktion
# Sprachkorrektur Diagnosen und Therapie
# diverse Routinen defs
# Möglichkeit für jedes Modell Besonderheiten bei Körperlicher Untersuchugn  zu definieren
# 
# 
#

import streamlit as st
from openai import OpenAI, RateLimitError
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
from module.fallverwaltung import (
    DEFAULT_FALLDATEI_URL,
    fallauswahl_prompt,
    lade_fallbeispiele,
    prepare_fall_session_state,
)
from module.fall_config import clear_fixed_scenario, get_fall_fix_state
from module.footer import copyright_footer

# Für Einbinden Supabase Tabellen

from supabase import create_client, Client
# Supabase initialisieren
supabase_url = st.secrets["supabase"]["url"]
supabase_key = st.secrets["supabase"]["key"]
supabase: Client = create_client(supabase_url, supabase_key)

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

def speichere_gpt_feedback_in_supabase():
    """Leitet die Supabase-Speicherung an das neue Hilfsmodul weiter."""

    # Die bisherige Implementierung wurde hier bewusst ersetzt, damit exakt dieselbe
    # Logik genutzt wird wie auf der dedizierten Feedback-Seite (``pages/6_Feedback.py``).
    # Dort wird der Feedback-Modus ("Client") bereits berücksichtigt und zuverlässig in
    # Supabase abgelegt. Durch die Bündelung vermeiden wir divergierende Datenstrukturen.
    speichere_feedback_mit_modus()

#---------------- Routinen Ende -------------------
initialisiere_session_state()

#####
# Testlauf
# diagnostik_und_befunde_routine(client)
# diagnostik_eingaben, gpt_befunde = diagnostik_und_befunde_routine(client, start_runde=2)
# anzahl_runden = st.session_state.get("diagnostik_runden_gesamt", 1)
# st.write ("Status:", diagnostik_eingaben, gpt_befunde, anzahl_runden)
#####

szenario_df = lade_fallbeispiele(url=DEFAULT_FALLDATEI_URL)
fixed, fixed_szenario = get_fall_fix_state()

if not szenario_df.empty:
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
                f"Das fixierte Szenario '{fixed_szenario}' ist nicht mehr verfügbar. "
                "Die Fixierung wurde aufgehoben."
            )
            clear_fixed_scenario()
            fallauswahl_prompt(szenario_df)
    elif "diagnose_szenario" not in st.session_state:
        fallauswahl_prompt(szenario_df)

if st.session_state.get("diagnose_szenario"):
    prepare_fall_session_state()

show_sidebar()

display_offline_banner()

# Anweisungen anzeigen
zeige_instruktionen_vor_start()

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
    with st.spinner(f"{st.session_state.patient_name} antwortet..."):
        try:
            init_token_counters()    
            response = client.chat.completions.create(
                model="gpt-4",
                messages=st.session_state.messages,
                temperature=0.6
            )
            add_usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
            reply = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": reply})
        except RateLimitError:
            st.error("🚫 Die Anfrage konnte nicht verarbeitet werden, da die OpenAI-API derzeit überlastet ist. Bitte versuchen Sie es in einigen Minuten erneut.")
    st.rerun()


# Abschnitt: Körperliche Untersuchung
st.markdown("---")
anzahl_fragen = sum(1 for m in st.session_state.messages if m["role"] == "user")

if anzahl_fragen > 0:
    st.subheader("Körperliche Untersuchung")

#Debug
    # st.write("Szenario:", st.session_state.diagnose_szenario)
    # st.write("Features:", st.session_state.diagnose_features)
    # st.write("Prompt:", st.session_state.SYSTEM_PROMPT)
    if "koerper_befund" in st.session_state:
        st.success("✅ Körperliche Untersuchung erfolgt.")
        st.markdown(st.session_state.koerper_befund)
    else:
        if st.button("Untersuchung durchführen"):
            with st.spinner(f"{st.session_state.patient_name} wird untersucht..."):
                try:
                    koerper_befund = generiere_koerperbefund(
                        client,
                        st.session_state.diagnose_szenario,
                        st.session_state.diagnose_features,
                        st.session_state.koerper_befund_tip
                    )
                    st.session_state.koerper_befund = koerper_befund
                    st.rerun()
                except RateLimitError:
                    st.error("🚫 Die Untersuchung konnte nicht erstellt werden. Die OpenAI-API ist derzeit überlastet.")
           
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
            # st.success("✅ Angaben gespeichert. Befunde können jetzt generiert werden.")
            st.rerun()

    else:
        # st.markdown("📝 **Ihre gespeicherten Eingaben:**")
        st.markdown(f"**Differentialdiagnosen:**  \n{st.session_state.user_ddx2}")
        st.markdown(f"**Diagnostische Maßnahmen:**  \n{st.session_state.user_diagnostics}")

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
    else:
        if st.button("🧪 Befunde generieren lassen"):
            from befundmodul import generiere_befund

            try:
                diagnostik_eingabe = st.session_state.user_diagnostics
                diagnose_szenario = st.session_state.diagnose_szenario

                with st.spinner("Befunde werden generiert..."):
                    befund = generiere_befund(client, diagnose_szenario, diagnostik_eingabe)

                st.session_state.befunde = befund
                st.success("✅ Befunde generiert")
                st.rerun()

            except RateLimitError:
                st.error("🚫 Befunde konnten nicht generiert werden. Die OpenAI-API ist aktuell überlastet.")
            except Exception as e:
                st.error(f"❌ Fehler bei der Befundgenerierung: {e}")

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
        with st.spinner("GPT erstellt Befunde..."):
            befund = generiere_befund(client, szenario, neue_diagnostik)
            st.session_state[f"befunde_runde_{neuer_termin}"] = befund
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
