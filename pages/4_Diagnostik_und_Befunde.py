import streamlit as st
from module.sidebar import show_sidebar
from module.footer import copyright_footer
from diagnostikmodul import diagnostik_und_befunde_routine
from befundmodul import generiere_befund
from module.offline import display_offline_banner, is_offline

show_sidebar()
display_offline_banner()

st.session_state.setdefault("befund_generating", False)
st.session_state.setdefault("befund_generierung_gescheitert", False)


def aktualisiere_kumulative_befunde_page(neuer_befund: str) -> None:
    """Pflegt den Primärbefund und die kumulativen Texte für Export/Feedback ein."""

    st.session_state["befunde"] = neuer_befund

    passagen = [f"### Termin 1\n{neuer_befund}".strip()]
    gesamt = st.session_state.get("diagnostik_runden_gesamt", 1)
    for termin in range(2, gesamt + 1):
        key = f"befunde_runde_{termin}"
        text = st.session_state.get(key, "").strip()
        if text:
            passagen.append(f"### Termin {termin}\n{text}")

    st.session_state["gpt_befunde"] = neuer_befund
    st.session_state["gpt_befunde_kumuliert"] = "\n---\n".join(passagen).strip()


def starte_automatische_befundgenerierung_page(client) -> None:
    """Startet ohne Nutzereingriff die Befundgenerierung, sobald alle Daten vorliegen."""

    if st.session_state.get("befund_generating", False):
        return
    if st.session_state.get("befunde"):
        return
    if st.session_state.get("befund_generierung_gescheitert", False):
        return
    if client is None:
        return  # Sicherheitsnetz, falls der Client nicht initialisiert wurde.

    diagnostik_text = st.session_state.get("user_diagnostics", "").strip()
    ddx_text = st.session_state.get("user_ddx2", "").strip()
    if not diagnostik_text or not ddx_text:
        return

    st.session_state["befund_generating"] = True
    st.session_state.pop("befund_generierungsfehler", None)

    try:
        szenario = st.session_state.get("diagnose_szenario", "")
        if is_offline():
            befund = generiere_befund(client, szenario, diagnostik_text)
        else:
            with st.spinner("Befunde werden automatisch generiert..."):
                befund = generiere_befund(client, szenario, diagnostik_text)
        aktualisiere_kumulative_befunde_page(befund)
    except Exception as error:
        st.session_state["befund_generierung_gescheitert"] = True
        st.session_state["befund_generierungsfehler"] = str(error)
    else:
        st.session_state["befund_generierung_gescheitert"] = False
    finally:
        st.session_state["befund_generating"] = False

    if not st.session_state.get("befund_generierung_gescheitert", False):
        st.rerun()

# st.subheader("Diagnostik und Befunde")

# --- Voraussetzungen wie in Hauptdatei beachten ---
if "koerper_befund" in st.session_state:
        if "user_ddx2" not in st.session_state:
                with st.form("differentialdiagnosen_diagnostik_formular"):
                    ddx_input2 = st.text_area("Welche drei Differentialdiagnosen halten Sie nach Anamnese und Untersuchung für möglich?", key="ddx_input2")
                    diag_input2 = st.text_area("Welche konkreten diagnostischen Maßnahmen möchten Sie vorschlagen?", key="diag_input2")
                    submitted_diag = st.form_submit_button("✅ Eingaben speichern")
        
                if submitted_diag:
                    from sprachmodul import sprach_check
                    client = st.session_state.get("openai_client")
                    st.session_state.user_ddx2 = sprach_check(ddx_input2, client)
                    st.session_state.user_diagnostics = sprach_check(diag_input2, client)
                    starte_automatische_befundgenerierung_page(client)

        else:
                st.markdown(f"**Differentialdiagnosen:**  \n{st.session_state.user_ddx2}")
                st.markdown(f"**Diagnostische Maßnahmen:**  \n{st.session_state.user_diagnostics}")

        starte_automatische_befundgenerierung_page(st.session_state.get("openai_client"))
else:
    st.subheader("Diagnostik und Befunde")
    st.button("Untersuchung durchführen", disabled=True)
    st.info("❗Bitte führen Sie zuerst die körperliche Untersuchung durch.")

# --- Befunde anzeigen oder generieren ---
st.markdown("---")

if (
    "koerper_befund" in st.session_state
    and "user_diagnostics" in st.session_state
    and "user_ddx2" in st.session_state
):
    st.subheader("📄 Befunde")

    if "befunde" in st.session_state:
        st.markdown(st.session_state.befunde)
        if st.session_state.get("befund_generierungsfehler"):
            st.info(
                "ℹ️ Der automatische Lauf meldete zuvor einen Fehler. Der Hinweis verbleibt zur Transparenz."
            )
    else:
        if st.session_state.get("befund_generierungsfehler"):
            st.error(
                "❌ Automatische Befundgenerierung fehlgeschlagen: "
                f"{st.session_state['befund_generierungsfehler']}"
            )
        if st.session_state.get("befund_generierung_gescheitert", False):
            client = st.session_state.get("openai_client")
            if st.button("🧪 Befunde generieren lassen"):
                try:
                    st.session_state["befund_generating"] = True
                    diagnostik_eingabe = st.session_state.user_diagnostics
                    diagnose_szenario = st.session_state.diagnose_szenario

                    if is_offline():
                        befund = generiere_befund(client, diagnose_szenario, diagnostik_eingabe)
                    else:
                        with st.spinner("Befunde werden erneut generiert..."):
                            befund = generiere_befund(client, diagnose_szenario, diagnostik_eingabe)

                    aktualisiere_kumulative_befunde_page(befund)
                    st.session_state["befund_generierung_gescheitert"] = False
                    st.session_state.pop("befund_generierungsfehler", None)
                    st.session_state["befund_generating"] = False
                    if is_offline():
                        st.info("🔌 Offline-Befund gespeichert. Für erneute KI-Ergebnisse kann der Online-Modus genutzt werden.")
                    st.success("✅ Befunde generiert")
                    st.rerun()

                except Exception as error:
                    st.session_state["befund_generating"] = False
                    st.error(f"❌ Manueller Fallback fehlgeschlagen: {error}")
                    # Hinweis: Zusätzliche Debug-Ausgaben können hier bei Bedarf ergänzt werden.
else:
    st.subheader("📄 Befunde")
    st.button("🧪 Befunde generieren lassen", disabled=True)
    st.info("❗Bitte fordern Sie zunächst Untersuchungen an.")

# Weitere Diagnostik-Termine
if not st.session_state.get("final_diagnose", "").strip():
    if (
        "diagnostik_eingaben" not in st.session_state
        or "gpt_befunde" not in st.session_state
        or st.session_state.get("diagnostik_aktiv", False)
    ):
        client = st.session_state.get("openai_client")
        diagnostik_eingaben, gpt_befunde = diagnostik_und_befunde_routine(
            client,
            start_runde=2,
            weitere_diagnostik_aktiv=False
        )
        st.session_state["diagnostik_eingaben"] = diagnostik_eingaben
        st.session_state["gpt_befunde"] = gpt_befunde
    else:
        diagnostik_eingaben = st.session_state["diagnostik_eingaben"]
        gpt_befunde = st.session_state["gpt_befunde"]

    # Anzeige bestehender Befunde
    gesamt = st.session_state.get("diagnostik_runden_gesamt", 1)
    for i in range(2, gesamt + 1):
        bef_key = f"befunde_runde_{i}"
        bef = st.session_state.get(bef_key, "")
        if bef:
            st.markdown(f"📅 Termin {i}")
            st.markdown(bef)

# Zusätzlicher Termin
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
        client = st.session_state.get("openai_client")
        if is_offline():
            befund = generiere_befund(client, szenario, neue_diagnostik)
        else:
            with st.spinner("GPT erstellt Befunde..."):
                befund = generiere_befund(client, szenario, neue_diagnostik)
        st.session_state[f"befunde_runde_{neuer_termin}"] = befund
        st.session_state["diagnostik_runden_gesamt"] = neuer_termin
        st.session_state["diagnostik_aktiv"] = False
        if is_offline():
            st.info("🔌 Offline-Befund gespeichert. Schalte den Online-Modus wieder ein, um echte GPT-Ergebnisse zu erhalten.")
        st.rerun()

# Button für neue Diagnostik
if (
    not st.session_state.get("diagnostik_aktiv", False)
    and ("befunde" in st.session_state or gesamt >= 2)
):
    if st.button("➕ Weitere Diagnostik anfordern", key="btn_neue_diagnostik"):
        st.session_state["diagnostik_aktiv"] = True
        st.rerun()

# # Nur für Admin sichtbar:
# if st.session_state.get("admin_mode"):
#     st.page_link("pages/20_Fallbeispiel_Editor.py", label="🔧 Fallbeispiel-Editor", icon="🔧")

# Weiter-Link zur Diagnose und Therapie
st.page_link(
    "pages/5_Diagnose_und_Therapie.py",
    label="Weiter zur Diagnose und Therapie",
    icon="💊",
    disabled="befunde" not in st.session_state
)

copyright_footer()

