import streamlit as st
from datetime import datetime
import streamlit.components.v1 as components
from module.untersuchungsmodul import (
    generiere_koerperbefund,
    generiere_sonderuntersuchung,
)
from module.navigation import redirect_to_start_page
from openai import RateLimitError
from module.sidebar import show_sidebar
from module.footer import copyright_footer
from module.offline import display_offline_banner, is_offline
from module.loading_indicator import task_spinner

copyright_footer()
show_sidebar()
display_offline_banner()

st.session_state.setdefault("koerper_befund_generating", False)
st.session_state.setdefault("sonder_untersuchung_generating", False)

# Die Eingabe für Sonderuntersuchungen erhält einen definierten Ausgangswert.
# So bleibt das Textfeld auch beim ersten Laden der Seite konsistent befüllt
# (hier: bewusst leer) und wir vermeiden Fehlermeldungen durch späte Zuweisungen.
st.session_state.setdefault("sonderuntersuchung_input", "")

# Falls ein vorheriger Durchlauf das Textfeld gezielt leeren wollte, wird dies
# hier umgesetzt. Die Pop-Operation erfolgt vor der Widget-Instanziierung,
# damit Streamlit keine Mutation eines bereits existierenden Widgets meldet.
if st.session_state.pop("sonderuntersuchung_input_leeren", False):
    st.session_state["sonderuntersuchung_input"] = ""


def aktualisiere_befundanzeige() -> None:
    """Bereitet den Basisbefund plus alle Zusatzblöcke für die Anzeige auf."""
    basis = st.session_state.get("koerper_befund_basis", "").strip()
    zusatzbloecke = [
        eintrag.get("anzeige", "").strip()
        for eintrag in st.session_state.get("sonderuntersuchungen", [])
        if eintrag.get("anzeige")
    ]
    teile = [abschnitt for abschnitt in [basis, *zusatzbloecke] if abschnitt]
    st.session_state["koerper_befund"] = "\n\n".join(teile).strip()


def aktualisiere_sonderdiagnostik_prefix() -> None:
    """Synchronisiert die Zusatzuntersuchungen mit dem Diagnostik-Export."""
    sonderliste = st.session_state.get("sonderuntersuchungen", [])
    if not sonderliste:
        st.session_state.pop("sonderdiagnostik_text", None)
        basis = st.session_state.get("diagnostik_eingaben_basis", "").strip()
        if basis:
            st.session_state["diagnostik_eingaben_kumuliert"] = basis
        elif "diagnostik_eingaben_kumuliert" in st.session_state:
            st.session_state["diagnostik_eingaben_kumuliert"] = ""
        return

    abschnitte = []
    for index, eintrag in enumerate(sonderliste, start=1):
        anforderung = eintrag.get("anforderung", "").strip()
        ergebnis = eintrag.get("diagnostik", "").strip()
        abschnitte.append(
            "\n".join(
                [
                    f"### Gesondert angeforderte Untersuchung {index}",
                    f"Anforderung: {anforderung or '(keine Angabe)'}",
                    "Ergebnis:",
                    ergebnis or "(kein Ergebnis hinterlegt)",
                ]
            ).strip()
        )

    sondertext = "\n\n".join(abschnitte).strip()
    st.session_state["sonderdiagnostik_text"] = sondertext
    basis = st.session_state.get("diagnostik_eingaben_basis", "").strip()
    if basis:
        st.session_state["diagnostik_eingaben_kumuliert"] = f"{sondertext}\n\n{basis}".strip()
    else:
        st.session_state["diagnostik_eingaben_kumuliert"] = sondertext


# Standardinitialisierung, damit nach Laden eines Falls konsistente Strukturen
# vorliegen und Debug-Ausgaben bei Bedarf darauf zugreifen können.
st.session_state.setdefault("sonderuntersuchungen", [])

if "koerper_befund" in st.session_state and "koerper_befund_basis" not in st.session_state:
    # Kompatibilitätsschicht für ältere SessionStates: Der vorhandene Text wird als
    # Basis übernommen, damit neue Zusatzblöcke korrekt angehängt werden können.
    st.session_state["koerper_befund_basis"] = st.session_state["koerper_befund"]

# Voraussetzungen prüfen
if (
    "diagnose_szenario" not in st.session_state or
    "patient_name" not in st.session_state or
    "patient_age" not in st.session_state or
    "patient_job" not in st.session_state or
    "diagnose_features" not in st.session_state
):
    redirect_to_start_page("⚠️ Der Fall ist noch nicht geladen. Bitte beginne über die Startseite.")

# Optional: Startzeit merken (z. B. für spätere Auswertung)
if "start_untersuchung" not in st.session_state:
    st.session_state.start_untersuchung = datetime.now()

# Körperlicher Befund generieren oder anzeigen

# Bedingung: mindestens eine Anamnesefrage gestellt
fragen_gestellt = any(m["role"] == "user" for m in st.session_state.get("messages", []))

if "koerper_befund" in st.session_state:
    # Bei jedem Seitenaufruf wird der Text aus Basis + Zusätzen neu zusammengesetzt,
    # damit nach einer Rerun-Operation keine veralteten Abschnitte sichtbar bleiben.
    aktualisiere_befundanzeige()
    st.success("✅ Körperliche Untersuchung erfolgt.")
    st.subheader("🔍 Befund")
    st.markdown(st.session_state.koerper_befund)

    st.markdown("---")
    st.subheader("➕ Gesonderte Untersuchungen anfordern")
    st.write(
        "Nutze das folgende Feld, um weiterführende körperliche Untersuchungen zu spezifizieren. "
        "Die Antworten werden direkt unter dem Ausgangsbefund ergänzt und in der Evaluation markiert."
    )
    sonder_input = st.text_area(
        "Welche spezielle Untersuchung möchtest du durchführen lassen?",
        key="sonderuntersuchung_input",
    )

    if st.button(
        "Anforderung absenden",
        disabled=st.session_state.get("sonder_untersuchung_generating", False)
        or st.session_state.get("koerper_befund_generating", False),
    ):
        if not sonder_input.strip():
            st.warning("Bitte gib eine konkrete Untersuchung an, bevor du absendest.")
        else:
            st.session_state["sonder_untersuchung_generating"] = True
            try:
                if is_offline():
                    sonder_befund = generiere_sonderuntersuchung(
                        st.session_state.get("openai_client"),
                        st.session_state.diagnose_szenario,
                        st.session_state.diagnose_features,
                        sonder_input,
                        st.session_state.get("koerper_befund_basis", ""),
                    )
                else:
                    sonderaufgaben = [
                        "Analysiere Anforderung",
                        "Beziehe bisherigen Befund ein",
                        "Formuliere Zusatzbefund",
                    ]
                    with task_spinner(
                        "Zusatzuntersuchung wird erstellt...",
                        sonderaufgaben,
                    ) as indikator:
                        indikator.advance(1)
                        sonder_befund = generiere_sonderuntersuchung(
                            st.session_state["openai_client"],
                            st.session_state.diagnose_szenario,
                            st.session_state.diagnose_features,
                            sonder_input,
                            st.session_state.get("koerper_befund_basis", ""),
                        )
                        indikator.advance(1)
                        indikator.advance(1)

                neuer_block = {
                    "anforderung": sonder_input.strip(),
                    "diagnostik": sonder_befund,
                    "anzeige": sonder_befund,
                }
                st.session_state["sonderuntersuchungen"].append(neuer_block)
                aktualisiere_befundanzeige()
                aktualisiere_sonderdiagnostik_prefix()
                st.session_state["sonder_untersuchung_generating"] = False
                # Anstatt das Textfeld direkt zu überschreiben, setzen wir eine
                # Zielmarke für den nächsten Durchlauf. Beim erneuten Rendern
                # wird das Feld vor der Widget-Erstellung geleert.
                st.session_state["sonderuntersuchung_input_leeren"] = True
                st.success("Die gesonderte Untersuchung wurde ergänzt.")
                st.rerun()
            except RateLimitError:
                st.session_state["sonder_untersuchung_generating"] = False
                st.error(
                    "🚫 Die Zusatzuntersuchung konnte nicht generiert werden. Die OpenAI-API ist aktuell ausgelastet."
                )
            except Exception as err:
                st.session_state["sonder_untersuchung_generating"] = False
                st.error(f"❌ Fehler bei der Zusatzuntersuchung: {err}")
                # Debug-Hinweis: Bei Bedarf kann hier temporär st.exception(err) aktiviert werden.

elif fragen_gestellt:
    if not st.session_state.get("koerper_befund_generating", False):
        st.session_state.koerper_befund_generating = True
        try:
            if is_offline():
                koerper_befund = generiere_koerperbefund(
                    st.session_state.get("openai_client"),
                    st.session_state.diagnose_szenario,
                    st.session_state.diagnose_features,
                    st.session_state.get("koerper_befund_tip", ""),
                )
                # Neuer Befund wird als Grundlage gespeichert und Zusatzlisten geleert,
                # damit Altlasten aus vorherigen Fällen nicht angezeigt werden.
                st.session_state.koerper_befund_basis = koerper_befund
                st.session_state["sonderuntersuchungen"] = []
                aktualisiere_befundanzeige()
                aktualisiere_sonderdiagnostik_prefix()
            else:
                untersuchungsaufgaben = [
                    "Sammle anamnestische Schlüsselhinweise",
                    "Berechne passende Untersuchungsbefunde",
                    "Bereite Ergebnistext für die Anzeige auf",
                ]
                with task_spinner(
                    f"{st.session_state.patient_name} wird untersucht...",
                    untersuchungsaufgaben,
                ) as indikator:
                    indikator.advance(1)
                    koerper_befund = generiere_koerperbefund(
                        st.session_state["openai_client"],
                        st.session_state.diagnose_szenario,
                        st.session_state.diagnose_features,
                        st.session_state.get("koerper_befund_tip", ""),
                    )
                    indikator.advance(1)
                    st.session_state.koerper_befund_basis = koerper_befund
                    st.session_state["sonderuntersuchungen"] = []
                    aktualisiere_befundanzeige()
                    aktualisiere_sonderdiagnostik_prefix()
                    indikator.advance(1)
            st.session_state.koerper_befund_generating = False
            if is_offline():
                st.info(
                    "🔌 Offline-Befund geladen. Sobald der Online-Modus aktiv ist, kannst du einen KI-generierten Befund abrufen."
                )
            st.rerun()
        except RateLimitError:
            st.session_state.koerper_befund_generating = False
            st.error("🚫 Die Untersuchung konnte nicht erstellt werden. Die OpenAI-API ist derzeit überlastet.")
        except Exception as err:
            st.session_state.koerper_befund_generating = False
            st.error(f"❌ Unerwarteter Fehler bei der Untersuchung: {err}")
        # Debug-Hinweis: Bei Bedarf kann hier kurzfristig st.write(...) ergänzt werden, um Zwischenstände sichtbar zu machen.

    if st.button(
        "🩺 Untersuchung durchführen",
        disabled=st.session_state.get("koerper_befund_generating", False),
    ):
        st.session_state.koerper_befund_generating = True
        try:
            if is_offline():
                koerper_befund = generiere_koerperbefund(
                    st.session_state.get("openai_client"),
                    st.session_state.diagnose_szenario,
                    st.session_state.diagnose_features,
                    st.session_state.get("koerper_befund_tip", "")
                )
                st.session_state.koerper_befund_basis = koerper_befund
                st.session_state["sonderuntersuchungen"] = []
                aktualisiere_befundanzeige()
                aktualisiere_sonderdiagnostik_prefix()
            else:
                untersuchungsaufgaben = [
                    "Sammle anamnestische Schlüsselhinweise",
                    "Berechne passende Untersuchungsbefunde",
                    "Bereite Ergebnistext für die Anzeige auf",
                ]
                with task_spinner(
                    f"{st.session_state.patient_name} wird untersucht...",
                    untersuchungsaufgaben,
                ) as indikator:
                    indikator.advance(1)
                    koerper_befund = generiere_koerperbefund(
                        st.session_state["openai_client"],
                        st.session_state.diagnose_szenario,
                        st.session_state.diagnose_features,
                        st.session_state.get("koerper_befund_tip", "")
                    )
                    indikator.advance(1)
                    st.session_state.koerper_befund_basis = koerper_befund
                    st.session_state["sonderuntersuchungen"] = []
                    aktualisiere_befundanzeige()
                    aktualisiere_sonderdiagnostik_prefix()
                    indikator.advance(1)
            st.session_state.koerper_befund_generating = False
            if is_offline():
                st.info("🔌 Offline-Befund geladen. Sobald der Online-Modus aktiv ist, kannst du einen KI-generierten Befund abrufen.")
            st.rerun()
        except RateLimitError:
            st.session_state.koerper_befund_generating = False
            st.error("🚫 Die Untersuchung konnte nicht erstellt werden. Die OpenAI-API ist derzeit überlastet.")
        except Exception as err:
            st.session_state.koerper_befund_generating = False
            st.error(f"❌ Unerwarteter Fehler bei der Untersuchung: {err}")
else:
    st.subheader("🩺 Untersuchung")
    st.button(
        "Untersuchung durchführen",
        disabled=True,
    )
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

