import streamlit as st

from module.admin_data import FeedbackExportError, build_feedback_export
from module.sidebar import show_sidebar
from module.footer import copyright_footer
from module.offline import display_offline_banner, is_offline
from module.fallverwaltung import (
    fallauswahl_prompt,
    get_verhaltensoptionen,
    lade_fallbeispiele,
    prepare_fall_session_state,
    reset_fall_session_state,
    speichere_fallbeispiel,
)
from module.fall_config import (
    clear_fixed_behavior,
    clear_fixed_scenario,
    get_behavior_fix_state,
    get_fall_fix_state,
    get_config_file_status,
    get_feedback_mode_fix_info,
    set_feedback_mode_fix,
    clear_feedback_mode_fix,
    set_fixed_behavior,
    set_fixed_scenario,
)
from module.mcp_client import get_amboss_configuration_status
from module.amboss_render import render_markdown_for_display
from module.feedback_mode import (
    FEEDBACK_MODE_AMBOSS_CHATGPT,
    FEEDBACK_MODE_CHATGPT,
    SESSION_KEY_EFFECTIVE_MODE,
    reset_random_mode,
    set_mode_override,
)
from module.amboss_preprocessing import get_cached_summary
from module.loading_indicator import task_spinner


copyright_footer()
show_sidebar()
display_offline_banner()


def _restart_application_after_offline() -> None:
    """Reset den Session State und startet die Anwendung neu."""

    reset_fall_session_state()
    preserve_keys = {"offline_mode", "is_admin"}
    for key in list(st.session_state.keys()):
        if key in preserve_keys:
            continue
        st.session_state.pop(key, None)
    st.rerun()

if not st.session_state.get("is_admin"):
    st.error("Kein Zugriff: Dieser Bereich steht nur Administrator*innen zur Verfügung.")
    st.info("Bitte gib in der Anamnese den gültigen Admin-Code ein, um Zugriff zu erhalten.")
    st.page_link("pages/1_Anamnese.py", label="Zurück zur Anamnese")
    st.stop()

st.title("Adminbereich")

# Der Statusüberblick ersetzt die Hinweise aus der Seitenleiste und bietet nun
# zentral sichtbar an, ob AMBOSS korrekt angebunden ist und ob die
# Konfigurationsdatei für Fixierungen verfügbar ist. Für Debugging kann der
# Abschnitt bei Bedarf erweitert werden (z. B. durch Ausgabe zusätzlicher
# Details).
st.subheader("Statusübersicht")

amboss_status = get_amboss_configuration_status()
if amboss_status.available:
    amboss_details = amboss_status.details or "AMBOSS MCP ist konfiguriert."
    st.success(f"✅ AMBOSS MCP bereit: {amboss_details}")
else:
    amboss_message = amboss_status.message or "AMBOSS MCP ist nicht konfiguriert."
    st.error(f"⚠️ AMBOSS MCP Problem: {amboss_message}")

# Zusätzlich zeigen wir an, ob bereits eine Antwort des MCP-Clients im
# Session State liegt. Das hilft beim Prüfen, ob ein Szenario bereits
# verarbeitet wurde.
if "amboss_result" in st.session_state:
    st.info("AMBOSS-Ergebnis geladen: Die Rückgabe steht für das Feedback bereit.")

    with st.expander("🧾 AMBOSS-MCP-Antwort einblenden"):
        # Der Expander zeigt die formatierte Markdown-Version der MCP-Antwort – exakt so,
        # wie sie im Testskript ``mcp_streamable_test`` dargestellt wird. Für
        # weiterführendes Debugging kann innerhalb des Try-Blocks eine zusätzliche
        # ``st.write``-Ausgabe aktiviert werden, um das Roh-JSON zu inspizieren.
        amboss_data = st.session_state.get("amboss_result")
        if amboss_data:
            try:
                pretty_md = render_markdown_for_display(amboss_data)
            except Exception as err:
                st.error(
                    "Die AMBOSS-Antwort konnte nicht formatiert werden. Bitte siehe die Kommentare"
                    " im Code für Debug-Hinweise (Details: {err}).".format(err=err)
                )
                # Debug-Hinweis: Bei Bedarf ``st.write(amboss_data)`` aktivieren, um das Rohobjekt
                # anzuzeigen und Formatprobleme zu identifizieren.
            else:
                st.code(pretty_md, language="markdown")
        else:
            st.caption("Im Session State liegt derzeit keine verwertbare AMBOSS-Antwort vor.")

    summary = get_cached_summary()
    with st.expander("🧠 GPT-Zusammenfassung der AMBOSS-Daten"):
        if summary:
            st.markdown(summary)
        else:
            st.caption(
                "Es wurde noch keine GPT-Zusammenfassung erzeugt. Sie entsteht automatisch, "
                "sobald das Feedback im kombinierten Modus generiert wird."
            )
else:
    st.info("Noch kein AMBOSS-Ergebnis im aktuellen Verlauf gespeichert.")

# Wenn lediglich ein fragmentarisches Ergebnis vorliegt, wird dieses klar
# gekennzeichnet. Administrator*innen sehen zusätzlich das konservierte
# Teilfragment, um bei Bedarf eigenständig zu prüfen, ob daraus weiterer
# Nutzen gezogen werden kann.
if st.session_state.get("amboss_result_unvollstaendig"):
    sicherungshinweis = st.session_state.get(
        "amboss_result_sicherung",
        {"hinweis": "Fragmentierte Antwort erkannt."},
    )
    st.warning(
        "⚠️ AMBOSS-Ergebnis unvollständig: {msg}".format(
            msg=sicherungshinweis.get(
                "hinweis",
                "Teilantwort gesichert, siehe Details unten.",
            )
        )
    )

    with st.expander("🧩 Gesicherte Teilantwort"):
        st.json(sicherungshinweis)

# Unabhängig vom Parsing-Erfolg kann hier ein Rohdatenschnappschuss aus dem MCP landen.
# Der separate Expander ermöglicht Administrator*innen, problematische Antworten
# komfortabel zu inspizieren und für die Fehlersuche zu kopieren. Die Daten stammen
# direkt aus dem Session State und werden nur angezeigt, wenn zuvor ein Fehler
# beim Parsing protokolliert wurde.
raw_debug_data = st.session_state.get("amboss_result_raw")
if raw_debug_data:
    with st.expander("🪵 AMBOSS-Rohdaten (Debug)"):
        if isinstance(raw_debug_data, dict):
            st.json(raw_debug_data)
        else:
            # Sollte der Eintrag ausnahmsweise kein Dictionary sein, zeigen wir ihn
            # als Klartext an. Damit bleibt die Darstellung robust, auch falls
            # künftig andere Module den Debug-Eintrag erweitern.
            st.code(str(raw_debug_data), language="json")

config_ok, config_message = get_config_file_status()
if config_ok:
    st.success(f"🗂️ Konfigurationsdatei: {config_message}")
else:
    st.error(f"🗂️ Konfigurationsdatei-Hinweis: {config_message}")

st.subheader("Verbindungsmodus")
current_offline = is_offline()
offline_toggle = st.toggle(
    "Offline-Modus aktivieren",
    value=current_offline,
    help=(
        "Im Offline-Modus werden statische Platzhalter statt GPT-Antworten verwendet. "
        "Die OpenAI-API wird dabei nicht angesprochen."
    ),
    key="admin_offline_toggle",
)

if offline_toggle != current_offline:
    st.session_state["offline_mode"] = offline_toggle
    if offline_toggle:
        st.info("Offline-Modus aktiviert. Alle Seiten nutzen jetzt statische Inhalte.")
    else:
        st.info("Online-Modus reaktiviert. Die Anwendung wird neu gestartet.")
        _restart_application_after_offline()

st.subheader("Feedback-Modus")
st.write(
    "Wähle hier, ob das Feedback zufällig oder gezielt mit AMBOSS-Bezug erstellt wird."
)

mode_options = {
    "🎲 Zufällige Auswahl (Standard)": None,
    "💬 Nur ChatGPT": FEEDBACK_MODE_CHATGPT,
    "🧠 ChatGPT + AMBOSS": FEEDBACK_MODE_AMBOSS_CHATGPT,
}

current_override = st.session_state.get("feedback_mode_override")
if current_override not in mode_options.values():
    current_override = None

labels = list(mode_options.keys())
default_index = labels.index(next(
    label for label, value in mode_options.items() if value == current_override
))

selected_label = st.radio(
    "Modus für künftige Feedback-Berechnungen",
    labels,
    index=default_index,
    help=(
        "Die Einstellung wirkt sich auf alle weiteren Feedback-Anfragen dieser Sitzung aus."
        " Bei Auswahl der Zufallsvariante wird der Modus bei der nächsten Generierung neu gelost."
    ),
)

selected_mode = mode_options[selected_label]
if selected_mode != current_override:
    if selected_mode is None:
        set_mode_override(None)
        reset_random_mode()
        clear_feedback_mode_fix()
        st.success("Zufällige Auswahl reaktiviert. Der Modus wird beim nächsten Feedback neu bestimmt.")
    else:
        set_mode_override(selected_mode)
        if selected_mode == FEEDBACK_MODE_AMBOSS_CHATGPT:
            set_feedback_mode_fix(selected_mode)
            st.success(
                "Übersteuerung aktiv: ChatGPT + AMBOSS wird verwendet und für zwei Stunden persistiert."
            )
        else:
            clear_feedback_mode_fix()
            st.success(f"Übersteuerung aktiv: {selected_mode} wird verwendet.")

effective_mode = st.session_state.get(SESSION_KEY_EFFECTIVE_MODE)
if effective_mode:
    st.caption(f"Aktuell gesetzter Modus für diese Sitzung: **{effective_mode}**")
else:
    st.caption("Noch kein Feedback erzeugt – der Modus wird beim ersten Aufruf festgelegt.")

persisted_active, persisted_value, remaining = get_feedback_mode_fix_info()
if persisted_active:
    minutes = int(remaining.total_seconds() // 60)
    st.caption(
        f"Persistente Einstellung aktiv: **{persisted_value}** (läuft in ca. {minutes} Minuten ab)."
    )
else:
    st.caption("Keine persistente ChatGPT+AMBOSS-Voreinstellung aktiv.")

st.subheader("Adminmodus")
st.write("Der Adminmodus ist aktiv. Bei Bedarf kannst du ihn hier wieder deaktivieren.")

if st.button("Adminmodus beenden", type="primary"):
    st.session_state["is_admin"] = False
    try:
        st.switch_page("pages/1_Anamnese.py")
    except Exception:
        st.experimental_set_query_params(page="1_Anamnese")
        st.rerun()

st.subheader("Fallverwaltung")

fall_df = lade_fallbeispiele(pfad="fallbeispiele.xlsx")

if fall_df.empty:
    st.info("Die Fallliste konnte nicht geladen werden. Bitte prüfe die Datei 'fallbeispiele.xlsx'.")
elif "Szenario" not in fall_df.columns:
    st.error("Die Fallliste enthält keine Spalte 'Szenario'.")
else:
    szenario_options = sorted(
        {str(s).strip() for s in fall_df["Szenario"].dropna() if str(s).strip()}
    )

    if not szenario_options:
        st.info("In der Datei wurden keine Szenarien gefunden.")
    else:
        # Wir lesen den aktuellen Status der Fixierungen aus, um Anzeige und Formular passend vorzubelegen.
        fixed, fixed_szenario = get_fall_fix_state()
        behavior_fixed, fixed_behavior_key = get_behavior_fix_state()
        aktuelles_szenario = st.session_state.get("diagnose_szenario") or st.session_state.get(
            "admin_selected_szenario"
        )
        aktuelles_verhalten_kurz = st.session_state.get("patient_verhalten_memo")
        aktuelles_verhalten_lang = st.session_state.get("patient_verhalten")
        # Die Verhaltensoptionen dienen als Auswahlgrundlage für das Admin-Formular.
        verhaltensoptionen = get_verhaltensoptionen()
        verhalten_option_keys = sorted(verhaltensoptionen.keys())

        szenario_text = (
            f"**Aktuelles Szenario:** {aktuelles_szenario}"
            if aktuelles_szenario
            else "Aktuell ist kein Szenario geladen."
        )

        if fixed and fixed_szenario:
            modus_text = (
                "**Modus:** Fixierter Fall – alle Nutzer*innen bearbeiten aktuell "
                f"'{fixed_szenario}'."
            )
        else:
            modus_text = "**Modus:** Zufälliger Fall – neue Sitzungen erhalten ein zufälliges Szenario."

        if behavior_fixed and fixed_behavior_key in verhaltensoptionen:
            verhaltensmodus_text = (
                "**Verhaltensmodus:** Fixiert – alle Sitzungen nutzen aktuell das vorgegebene Verhalten."
            )
        else:
            verhaltensmodus_text = (
                "**Verhaltensmodus:** Zufällig – das Verhalten wird bei jeder Sitzung neu bestimmt."
            )

        if aktuelles_verhalten_kurz and aktuelles_verhalten_lang:
            verhalten_text = (
                "**Patient*innenverhalten:** "
                f"{aktuelles_verhalten_kurz.capitalize()} – {aktuelles_verhalten_lang}"
            )
        elif aktuelles_verhalten_lang:
            verhalten_text = f"**Patient*innenverhalten:** {aktuelles_verhalten_lang}"
        else:
            verhalten_text = "Für das aktuelle Szenario ist kein Verhalten gesetzt."

        st.info(
            f"{szenario_text}\n\n{modus_text}\n\n{verhaltensmodus_text}\n\n{verhalten_text}"
        )

        with st.form("admin_fallauswahl"):
            if fixed and fixed_szenario in szenario_options:
                default_index = szenario_options.index(fixed_szenario)
            elif aktuelles_szenario in szenario_options:
                default_index = szenario_options.index(aktuelles_szenario)
            else:
                default_index = 0

            ausgewaehltes_szenario = st.selectbox(
                "Szenario auswählen",
                szenario_options,
                index=default_index,
                help="Wähle das Fallszenario aus, das für die nächste Sitzung verwendet werden soll.",
            )
            fall_fix_toggle = st.toggle(
                "Fall fixieren",
                value=fixed,
                help=(
                    "Aktiviere diese Option, damit alle künftigen Sitzungen dieses Szenario erhalten. "
                    "Wird die Fixierung aufgehoben, wählen nachfolgende Sitzungen wieder zufällig."
                ),
            )

            if behavior_fixed and fixed_behavior_key in verhalten_option_keys:
                default_behavior_index = verhalten_option_keys.index(fixed_behavior_key)
            elif aktuelles_verhalten_kurz in verhalten_option_keys:
                default_behavior_index = verhalten_option_keys.index(aktuelles_verhalten_kurz)
            else:
                default_behavior_index = 0

            ausgewaehltes_verhalten = st.selectbox(
                "Patient*innenverhalten auswählen",
                verhalten_option_keys,
                index=default_behavior_index,
                help=(
                    "Lege das gewünschte Verhalten fest. Über den Fixierschalter kannst du bestimmen, ob es für alle "
                    "Sitzungen gilt oder weiterhin zufällig gewählt wird."
                ),
                format_func=lambda key: f"{key.capitalize()} – {verhaltensoptionen[key]}",
            )
            verhalten_fix_toggle = st.toggle(
                "Patient*innenverhalten fixieren",
                value=behavior_fixed and fixed_behavior_key in verhalten_option_keys,
                help=(
                    "Aktiviere diese Option, damit alle künftigen Sitzungen dieses Verhalten nutzen. "
                    "Ohne Fixierung wird pro Sitzung zufällig ausgewählt."
                ),
            )
            bestaetigt = st.form_submit_button("Auswahl übernehmen", type="primary")

        if bestaetigt and ausgewaehltes_szenario:
            reset_fall_session_state()
            if fall_fix_toggle:
                fallauswahl_prompt(fall_df, ausgewaehltes_szenario)
                set_fixed_scenario(ausgewaehltes_szenario)
                st.session_state["admin_selected_szenario"] = ausgewaehltes_szenario
            else:
                clear_fixed_scenario()
                st.session_state.pop("admin_selected_szenario", None)
                fallauswahl_prompt(fall_df)

            if verhalten_fix_toggle and ausgewaehltes_verhalten:
                set_fixed_behavior(ausgewaehltes_verhalten)
            else:
                clear_fixed_behavior()

            prepare_fall_session_state()
            try:
                st.switch_page("pages/1_Anamnese.py")
            except Exception:
                st.rerun()

    st.divider()
    st.subheader("Neues Fallbeispiel")

    formular_state_key = "admin_fallformular_offen"
    if formular_state_key not in st.session_state:
        st.session_state[formular_state_key] = False

    if st.button("Neues Fallbeispiel hinzufügen", type="secondary"):
        st.session_state[formular_state_key] = True

    if st.session_state.get(formular_state_key):
        if st.button("Abbrechen", type="secondary"):
            st.session_state[formular_state_key] = False
            for key in list(st.session_state.keys()):
                if key.startswith("admin_neuer_fall_"):
                    st.session_state[key] = ""
            st.rerun()

        erforderliche_spalten = [
            "Szenario",
            "Beschreibung",
            "Körperliche Untersuchung",
            "Alter",
            "Geschlecht",
        ]

        vorhandene_spalten = list(fall_df.columns) if not fall_df.empty else []
        optionale_spalten = [
            spalte for spalte in vorhandene_spalten if spalte not in erforderliche_spalten
        ]

        for spalte in erforderliche_spalten:
            if spalte not in vorhandene_spalten:
                vorhandene_spalten.append(spalte)

        for spalte in erforderliche_spalten + optionale_spalten:
            state_key = f"admin_neuer_fall_{spalte}"
            if state_key not in st.session_state:
                st.session_state[state_key] = ""

        with st.form("admin_neues_fallbeispiel"):
            formularwerte: dict[str, str] = {}

            for spalte in erforderliche_spalten:
                widget_key = f"admin_neuer_fall_{spalte}"
                if spalte in {"Beschreibung", "Körperliche Untersuchung"}:
                    formularwerte[spalte] = st.text_area(spalte, key=widget_key)
                else:
                    formularwerte[spalte] = st.text_input(spalte, key=widget_key)

            for spalte in optionale_spalten:
                widget_key = f"admin_neuer_fall_{spalte}"
                formularwerte[spalte] = st.text_input(spalte, key=widget_key)

            abgesendet = st.form_submit_button("Fallbeispiel speichern", type="primary")

        if abgesendet:
            fehlermeldungen: list[str] = []
            neuer_fall: dict[str, object] = {}

            for spalte in erforderliche_spalten:
                wert = formularwerte.get(spalte, "")
                if not str(wert).strip():
                    fehlermeldungen.append(f"Bitte fülle das Feld '{spalte}' aus.")
                else:
                    neuer_fall[spalte] = str(wert).strip()

            for spalte in optionale_spalten:
                optional_wert = str(formularwerte.get(spalte, "")).strip()
                neuer_fall[spalte] = optional_wert if optional_wert else None

            alter_wert = str(neuer_fall.get("Alter", "")).strip()
            if alter_wert:
                try:
                    neuer_fall["Alter"] = int(float(alter_wert))
                except ValueError:
                    fehlermeldungen.append("Das Feld 'Alter' muss eine Zahl sein.")

            if fehlermeldungen:
                st.error("\n".join(fehlermeldungen))
            else:
                aktualisiert, fehler = speichere_fallbeispiel(
                    neuer_fall, pfad="fallbeispiele.xlsx"
                )
                if fehler:
                    st.error(f"Speichern fehlgeschlagen: {fehler}")
                elif aktualisiert is None:
                    st.error("Speichern fehlgeschlagen: Unerwarteter Fehler.")
                else:
                    fall_df = aktualisiert
                    st.success("Fallbeispiel wurde erfolgreich gespeichert.")
                    st.session_state[formular_state_key] = False
                    for key in list(st.session_state.keys()):
                        if key.startswith("admin_neuer_fall_"):
                            st.session_state[key] = ""

st.subheader("Feedback-Export")

DEFAULT_EXPORT_FILENAME = "feedback_gpt.xlsx"

def _reset_feedback_export_state() -> None:
    """Ensure the feedback export values stay valid and consistent."""

    st.session_state["feedback_export_bytes"] = b""
    st.session_state["feedback_export_filename"] = DEFAULT_EXPORT_FILENAME


def _prepare_feedback_export() -> None:
    """Build the feedback export and keep the UI state in sync."""

    st.session_state["feedback_export_error"] = ""
    ladeaufgaben = [
        "Verbinde mit Supabase",
        "Lade aktuelle Feedback-Datensätze",
        "Bereite Exportdatei auf",
    ]
    with task_spinner("Supabase-Daten werden geladen...", ladeaufgaben) as indikator:
        try:
            indikator.advance(1)
            export_bytes, export_filename = build_feedback_export()
            indikator.advance(1)
        except FeedbackExportError as exc:
            _reset_feedback_export_state()
            st.session_state["feedback_export_error"] = f"Export nicht möglich: {exc}"
        except Exception as exc:  # pragma: no cover - defensive
            _reset_feedback_export_state()
            st.session_state["feedback_export_error"] = f"Unerwarteter Fehler beim Export: {exc}"
        else:
            if not isinstance(export_bytes, (bytes, bytearray)):
                _reset_feedback_export_state()
                st.session_state[
                    "feedback_export_error"
                ] = "Ungültige Exportdaten erhalten. Bitte erneut versuchen."
            else:
                st.session_state["feedback_export_bytes"] = bytes(export_bytes)
                st.session_state["feedback_export_filename"] = (
                    export_filename or DEFAULT_EXPORT_FILENAME
                )
                st.session_state["feedback_export_revision"] += 1
                indikator.advance(1)


if "feedback_export_bytes" not in st.session_state:
    _reset_feedback_export_state()

if not isinstance(st.session_state.get("feedback_export_bytes"), bytes):
    _reset_feedback_export_state()

if "feedback_export_revision" not in st.session_state:
    st.session_state["feedback_export_revision"] = 0

if "feedback_export_error" not in st.session_state:
    st.session_state["feedback_export_error"] = ""

if st.button("Feedback-Export aktualisieren", type="secondary"):
    _reset_feedback_export_state()
    _prepare_feedback_export()

export_bytes = st.session_state.get("feedback_export_bytes", b"") or b""
export_filename = (
    st.session_state.get("feedback_export_filename", DEFAULT_EXPORT_FILENAME)
    or DEFAULT_EXPORT_FILENAME
)
download_ready = bool(export_bytes)
download_key = f"feedback_export_button_{st.session_state['feedback_export_revision']}"

download_placeholder = st.empty()

if download_ready:
    download_placeholder.download_button(
        "Feedback-Daten als Excel herunterladen",
        data=export_bytes,
        file_name=export_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        key=download_key,
    )
    st.success("Der aktuelle Feedback-Export steht zum Download bereit.")
else:
    download_placeholder.button(
        "Feedback-Daten als Excel herunterladen",
        disabled=True,
        key=f"{download_key}_placeholder",
    )
    st.info("Bitte aktualisiere den Export, bevor du die Excel-Datei herunterlädst.")

if st.session_state.get("feedback_export_error"):
    st.error(st.session_state["feedback_export_error"])
