# """Hilfsfunktionen zur Verwaltung und Auswahl der Fallszenarien."""
from __future__ import annotations

import random
from typing import Any, Iterable, Mapping

import pandas as pd
import streamlit as st
from supabase import Client, create_client

from module.patient_language import get_patient_forms
from module.MCP_Amboss import call_amboss_search
from module.amboss_preprocessing import ensure_amboss_summary, clear_cached_summary
from module.loading_indicator import task_spinner
from module.fall_config import (
    AMBOSS_FETCH_ALWAYS,
    AMBOSS_FETCH_IF_EMPTY,
    AMBOSS_FETCH_RANDOM,
    clear_fixed_behavior,
    get_amboss_fetch_preferences,
    get_behavior_fix_state,
)

_AMBOSS_INPUT_COLUMN = "Amboss_Input"
_AMBOSS_PERSIST_STATE_KEY = "amboss_persist_info"

# Name der Supabase-Tabelle, in der sämtliche Fallszenarien abgelegt werden.
_FALL_TABLE_NAME = "fallbeispiele"

# Abbildung zwischen Supabase-Spalten (snake_case) und den bisherigen DataFrame-
# Spalten mit deutschsprachigen Bezeichnungen. So bleibt die bestehende
# Verarbeitung kompatibel, obwohl die Datenquelle gewechselt wurde.
_SUPABASE_TO_DF: dict[str, str] = {
    "id": "id",
    "szenario": "Szenario",
    "beschreibung": "Beschreibung",
    "koerperliche_untersuchung": "Körperliche Untersuchung",
    "besonderheit": "Besonderheit",
    "alter": "Alter",
    "geschlecht": "Geschlecht",
    "amboss_input": _AMBOSS_INPUT_COLUMN,
    "created_at": "created_at",
    "updated_at": "updated_at",
}

# Umkehrabbildung zur komfortablen Erstellung von Insert- bzw. Update-Payloads.
_DF_TO_SUPABASE: dict[str, str] = {
    df_name: sb_name for sb_name, df_name in _SUPABASE_TO_DF.items() if df_name
}

_FALL_SESSION_KEYS: set[str] = {
    "diagnose_szenario",
    "diagnose_features",
    "koerper_befund_tip",
    "patient_alter_basis",
    "patient_gender",
    "patient_name",
    "patient_age",
    "patient_job",
    "patient_verhalten_memo",
    "patient_verhalten",
    "patient_hauptanweisung",
    "SYSTEM_PROMPT",
    "startzeit",
    "start_untersuchung",
    "untersuchung_done",
    "diagnostik_aktiv",
    "diagnostik_runden_gesamt",
    "messages",
    "koerper_befund",
    "user_ddx2",
    "user_diagnostics",
    "befunde",
    "diagnostik_eingaben",
    "gpt_befunde",
    "diagnostik_eingaben_kumuliert",
    "gpt_befunde_kumuliert",
    "final_diagnose",
    "therapie_vorschlag",
    "final_feedback",
    "feedback_prompt_final",
    "feedback_row_id",
    "student_evaluation_done",
    "token_sums",
}

_FALL_SESSION_PREFIXES: tuple[str, ...] = (
    "diagnostik_runde_",
    "befunde_runde_",
)


def _get_supabase_client() -> Client:
    """Erstellt einen authentifizierten Supabase-Client aus den Streamlit-Secrets."""

    supabase_config = st.secrets.get("supabase")
    if not supabase_config:
        raise RuntimeError(
            "Supabase-Konfiguration fehlt in st.secrets. Bitte die Sektion 'supabase' ergänzen."
        )

    try:
        url = supabase_config["url"]
        key = supabase_config["key"]
    except KeyError as exc:
        raise RuntimeError(
            "Supabase-Zugangsdaten unvollständig. Erwartet werden Schlüssel 'url' und 'key'."
        ) from exc

    try:
        return create_client(url, key)
    except Exception as exc:  # pragma: no cover - Netzwerkkonnektivität lässt sich schlecht testen
        raise RuntimeError(
            "Verbindung zu Supabase konnte nicht aufgebaut werden. Hinweise siehe Kommentare im Code."
        ) from exc


def _extract_amboss_input(fall: pd.Series) -> str:
    """Liest den gespeicherten AMBOSS-Text aus der Fallzeile."""

    value = fall.get(_AMBOSS_INPUT_COLUMN, "")
    if pd.isna(value):
        return ""
    return str(value).strip()


def _should_refresh_amboss_input(*, stored_value: str, mode: str, probability: float) -> bool:
    """Entscheidet anhand der Admin-Konfiguration, ob der MCP neu abgefragt wird."""

    if not stored_value:
        return True
    if mode == AMBOSS_FETCH_ALWAYS:
        return True
    if mode == AMBOSS_FETCH_IF_EMPTY:
        return False
    # Für den Zufallsmodus gilt: Ein Wert <= 0 verhindert neue Abrufe, ein Wert >= 1
    # sorgt für einen sicheren Abruf. Dazwischen wird klassisch gewürfelt.
    if probability <= 0:
        return False
    if probability >= 1:
        return True
    return random.random() < probability


def _persist_amboss_input(*, row_id: Any, value: str) -> tuple[bool, str | None]:
    """Schreibt die generierte Zusammenfassung in die Supabase-Tabelle."""

    if not value:
        return False, "Kein Text vorhanden – es wurde nichts gespeichert."

    try:
        fall_id = int(row_id)
    except (TypeError, ValueError):
        st.error(
            "❌ Die AMBOSS-Zusammenfassung konnte nicht gespeichert werden: Ungültige Fall-ID."
        )
        return False, "Fehler: Die Fall-ID ist ungültig oder fehlt."

    try:
        client = _get_supabase_client()
    except RuntimeError as exc:
        st.error(f"❌ Supabase nicht erreichbar: {exc}")
        st.info(
            "Debug-Hinweis: Bitte prüfe die Einträge in st.secrets['supabase'] und die Netzwerkverbindung."
        )
        return False, "Supabase-Verbindung fehlgeschlagen."

    payload = {"amboss_input": value}

    try:
        response = client.table(_FALL_TABLE_NAME).update(payload).eq("id", fall_id).execute()
    except Exception as exc:  # pragma: no cover - Netzwerkaussetzer lassen sich schwer simulieren
        st.error(f"❌ Aktualisierung der Supabase-Tabelle fehlgeschlagen: {exc}")
        st.info(
            "Debug-Hinweis: Überprüfe die Tabellenberechtigungen und die Netzwerklatenz."
        )
        return False, "Fehler beim Schreiben in die Supabase-Tabelle."

    if getattr(response, "error", None):
        st.error(
            "❌ Supabase meldet einen Fehler bei der Aktualisierung: {err}.".format(
                err=response.error
            )
        )
        return False, "Supabase hat den Update-Vorgang mit einer Fehlermeldung abgebrochen."

    if not response.data:
        st.warning(
            "⚠️ Supabase meldete keinen aktualisierten Datensatz. Bitte kontrolliere, ob die ID existiert."
        )
        return False, "Kein Datensatz mit der angegebenen ID gefunden."

    return True, "Zusammenfassung erfolgreich gespeichert."


def _clear_amboss_session_cache() -> None:
    """Entfernt alle AMBOSS-bezogenen Session-Werte für ein sauberes Szenario."""

    st.session_state.pop("amboss_result", None)
    st.session_state.pop("amboss_result_inner", None)
    st.session_state.pop("amboss_result_raw", None)
    st.session_state.pop("amboss_result_unvollstaendig", None)
    st.session_state.pop("amboss_result_sicherung", None)
    clear_cached_summary()
    st.session_state.pop("amboss_summary_source", None)


def _protokolliere_amboss_status(*, status: str, hinweis: str, quelle: str | None = None) -> None:
    """Hinterlegt den letzten Persistierungsstatus für den Adminbereich.

    Die Informationen landen gesammelt im Session State, damit Administrator*innen
    jederzeit nachvollziehen können, ob der Supabase-Eintrag erfolgte, übersprungen
    oder durch eine Einstellung verhindert wurde. ``quelle`` beschreibt optional,
    ob der Text aus Supabase, dem MCP oder einem Fallback stammt.
    """

    st.session_state[_AMBOSS_PERSIST_STATE_KEY] = {
        "status": status,
        "hinweis": hinweis,
        "quelle": quelle or "unbekannt",
    }

# Übersicht aller verfügbaren Verhaltensoptionen mit sprechenden Beschreibungen. Die Schlüssel werden im
# Session State abgelegt, damit eine Fixierung administrativ gesteuert werden kann.
_VERHALTENSOPTIONEN: dict[str, str] = {
    "knapp": "Beantworte Fragen grundsätzlich sehr knapp. Gib nur so viele Informationen preis, wie direkt erfragt wurden.",
    "redselig": "Beginne Antworten gern mit kleinen Anekdoten über Alltag, Beruf oder Familie. Gehe auf medizinische Fragen nur beiläufig - aber korrekt - ein und lenke bei manchen Fragen wieder auf private Themen um.",
    "ängstlich": "Wirke angespannt und vorsichtig, erwähne konkrete Sorgen (z. B. vor Krankenhaus oder Krebs) nur, wenn die Fragen darauf hindeuten, und vermeide Wiederholungen. ",
    "wissbegierig": "Wirke vorbereitet, zitiere gelegentlich medizinische Begriffe aus Internetrecherchen und frage aktiv nach Differenzialdiagnosen, Untersuchungen oder Leitlinien.",
    "verharmlosend": "Spiele Beschwerden konsequent herunter, nutze variierende Phrasen wie ‚Ist nicht so schlimm‘, vermeide Wiederholungen. Gib Symptome erst auf konkrete Nachfrage preis und betone, dass du eigentlich gesund wirken möchtest.",
}


def get_verhaltensoptionen() -> dict[str, str]:
    """Gibt eine Kopie der Verhaltensoptionen zurück."""

    return dict(_VERHALTENSOPTIONEN)

def lade_fallbeispiele() -> pd.DataFrame:
    """Liest alle Fallbeispiele aus der Supabase-Tabelle ein."""

    try:
        client = _get_supabase_client()
    except RuntimeError as exc:
        st.error(f"❌ Supabase nicht erreichbar: {exc}")
        st.info(
            "Debug-Hinweis: Bitte prüfe die Supabase-Konfiguration in st.secrets sowie die Netzwerkverbindung."
        )
        return pd.DataFrame(columns=list(_SUPABASE_TO_DF.values()))

    try:
        response = (
            client.table(_FALL_TABLE_NAME)
            .select('*')
            .order('szenario', desc=False)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - Netzwerkaussetzer lassen sich schwer simulieren
        st.error(f"❌ Abruf der Supabase-Tabelle '{_FALL_TABLE_NAME}' fehlgeschlagen: {exc}")
        st.info(
            "Debug-Hinweis: Nutze bei Bedarf die Supabase-Konsole, um Logs und Berechtigungen zu kontrollieren."
        )
        return pd.DataFrame(columns=list(_SUPABASE_TO_DF.values()))

    if getattr(response, 'error', None):
        st.error(
            "❌ Supabase meldet einen Fehler beim Laden der Fallliste: {err}.".format(
                err=response.error
            )
        )
        return pd.DataFrame(columns=list(_SUPABASE_TO_DF.values()))

    rows = response.data or []
    if not rows:
        # Leere Tabelle: Wir geben ein strukturiertes, aber leeres DataFrame zurück.
        return pd.DataFrame(columns=list(_SUPABASE_TO_DF.values()))

    df = pd.DataFrame(rows)
    df = df.rename(columns=_SUPABASE_TO_DF)

    # Sicherstellen, dass alle erwarteten Spalten vorhanden sind. Fehlende Werte werden als leere Strings
    # bzw. ``None`` ergänzt, damit nachfolgende Verarbeitungsschritte nicht ins Leere laufen.
    for spalte in _DF_TO_SUPABASE.keys():
        if spalte not in df.columns:
            df[spalte] = None

    # Die ID wird als Index genutzt, damit Updates (z. B. für AMBOSS-Zusammenfassungen) zielgerichtet erfolgen können.
    if 'id' in df.columns:
        try:
            df['id'] = df['id'].astype(int)
        except Exception:
            # Falls die Konvertierung fehlschlägt, belassen wir den Rohwert und geben einen Hinweis.
            st.info(
                "Debug-Hinweis: Mindestens eine Fall-ID ließ sich nicht in einen Integer konvertieren. Bitte Supabase prüfen."
            )
        df = df.set_index('id', drop=False)
    else:
        df.index = pd.RangeIndex(start=0, stop=len(df))

    return df





def speichere_fallbeispiel(
    row: Mapping[str, Any] | dict[str, Any],
) -> tuple[pd.DataFrame | None, str | None]:
    """Speichert ein neues Fallszenario in Supabase und liefert die aktualisierte Tabelle."""

    try:
        client = _get_supabase_client()
    except RuntimeError as exc:
        return None, f"Supabase-Verbindung fehlgeschlagen: {exc}"

    payload: dict[str, Any] = {}
    for df_spalte, wert in dict(row).items():
        supabase_spalte = _DF_TO_SUPABASE.get(df_spalte)
        if not supabase_spalte:
            continue  # Unbekannte Felder werden ignoriert, damit das Schema stabil bleibt.
        if isinstance(wert, str):
            wert = wert.strip()
            if not wert:
                wert = None
        if df_spalte == "Alter" and wert is not None:
            try:
                wert = int(wert)
            except (TypeError, ValueError):
                return None, "Das Feld 'Alter' konnte nicht als Zahl gespeichert werden."
        payload[supabase_spalte] = wert

    if 'szenario' not in payload or not payload['szenario']:
        return None, "Pflichtfeld 'Szenario' fehlt."

    try:
        response = client.table(_FALL_TABLE_NAME).insert(payload).execute()
    except Exception as exc:  # pragma: no cover - Netzwerkaussetzer lassen sich schwer simulieren
        return None, f"Speichern in Supabase fehlgeschlagen: {exc}"

    if getattr(response, 'error', None):
        return None, f"Supabase meldet einen Fehler: {response.error}"

    # Nach erfolgreichem Insert wird die aktuelle Tabelle erneut geladen, damit Admin-UI und Session-State synchron bleiben.
    return lade_fallbeispiele(), None





def fallauswahl_prompt(
    df: pd.DataFrame, szenario: str | None = None
) -> None:
    """Übernimmt ein zufälliges oder vorgegebenes Szenario in den Session State.

    Zusätzlich wird der AMBOSS-Input gepflegt. Wenn bereits eine Zusammenfassung in
    Supabase hinterlegt ist, wird sie aus der Spalte ``Amboss_Input`` übernommen
    und kein erneuter MCP-Aufruf ausgelöst. Fehlt der Eintrag oder wurde per
    Admin-Einstellung ein Refresh erzwungen, erfolgt ein Abruf inklusive erneuter
    GPT-Zusammenfassung. Das Ergebnis landet anschließend wieder in Supabase,
    damit zukünftige Sitzungen ohne MCP-Aufruf starten können.
    """

    if df.empty:
        st.error("📄 Die Falltabelle ist leer oder konnte nicht geladen werden.")
        _protokolliere_amboss_status(
            status="fehler",
            hinweis="Falltabelle leer oder nicht geladen – kein AMBOSS-Abgleich möglich.",
            quelle="keine",
        )
        return

    try:
        fall = _waehle_fall(df, szenario)
        fall_id = fall.get('id', fall.name)
    except (IndexError, KeyError, ValueError) as exc:
        st.error(f"❌ Fehler beim Auswählen des Falls: {exc}")
        _protokolliere_amboss_status(
            status="fehler",
            hinweis="Fall konnte nicht ausgewählt werden – siehe Fehlermeldung.",
            quelle="keine",
        )
        return
    except Exception as exc:  # pragma: no cover - defensive fallback
        st.error(f"❌ Unerwarteter Fehler beim Laden des Falls: {exc}")
        _protokolliere_amboss_status(
            status="fehler",
            hinweis="Unerwarteter Fehler bei der Fallauswahl – Details siehe Fehlermeldung.",
            quelle="keine",
        )
        return

    ladeaufgaben = [
        "Übernehme zufällig ausgewähltes Fallszenario",
        "Prüfe und sichere Zusammenfassung",
        "Fasse Ergebnisse zusammen",
    ]

    # Der Task-Spinner visualisiert transparent, welche Arbeitsschritte während
    # der Fallvorbereitung laufen. Das erleichtert sowohl Studierenden als auch
    # uns Entwickelnden das Verständnis, wo sich der Ladevorgang gerade befindet.
    with task_spinner(" Fallvorbereitung läuft...", ladeaufgaben) as indikator:
        st.session_state.diagnose_szenario = fall.get("Szenario", "")
        st.session_state.diagnose_features = fall.get("Beschreibung", "")
        st.session_state.koerper_befund_tip = fall.get("Körperliche Untersuchung", "")

        alter_roh = fall.get("Alter")
        try:
            alter_berechnet = int(float(alter_roh)) if alter_roh not in (None, "") else None
        except (TypeError, ValueError):
            alter_berechnet = None
        st.session_state.patient_alter_basis = alter_berechnet

        geschlecht = str(fall.get("Geschlecht", "")).strip().lower()
        if geschlecht == "n":
            geschlecht = random.choice(["m", "w"])
        elif geschlecht not in {"m", "w"}:
            geschlecht = ""
        st.session_state.patient_gender = geschlecht

        # Nach den Grunddaten signalisieren wir den Abschluss des ersten
        # Schritts. Falls das Debugging eine feinere Granularität benötigt,
        # kann hier temporär ein ``st.write`` aktiviert werden.
        indikator.advance(1)

        # Sobald das Szenario feststeht, wird es direkt an den MCP-Client von
        # AMBOSS übergeben. Bei Fehlern halten wir den Fortschritt dennoch
        # konsistent, damit Nutzer:innen nicht in einem ewigen Ladezustand
        # verbleiben.
        stored_amboss_input = _extract_amboss_input(fall)
        fetch_mode, fetch_probability = get_amboss_fetch_preferences()
        fetch_required = _should_refresh_amboss_input(
            stored_value=stored_amboss_input,
            mode=fetch_mode,
            probability=fetch_probability,
        )

        fetch_successful = False
        persist_status: str | None = None
        persist_hint: str | None = None
        persist_source: str | None = None

        if st.session_state.diagnose_szenario and fetch_required:
            try:
                call_amboss_search(query=st.session_state.diagnose_szenario)
            except Exception as exc:  # pragma: no cover - reine Laufzeitfehlerbehandlung
                st.error(
                    "❌ Abruf des AMBOSS-Inhalts zum Szenario fehlgeschlagen: "
                    f"{exc}"
                )
            else:
                fetch_successful = True
        else:
            # Falls kein Abruf erfolgt, werden eventuell verbliebene Daten aus
            # vorherigen Sitzungen entfernt. Damit verhindern wir, dass ein
            # gespeichertes Szenario versehentlich den Payload eines anderen
            # Falls referenziert.
            _clear_amboss_session_cache()
        indikator.advance(1)

        client = st.session_state.get("openai_client")
        patient_age_for_summary = st.session_state.get("patient_age")
        if patient_age_for_summary is None:
            patient_age_for_summary = st.session_state.get("patient_alter_basis")

        summary_text = stored_amboss_input
        if (
            fetch_successful
            and client
            and st.session_state.diagnose_szenario
            and patient_age_for_summary is not None
        ):
            try:
                generated_summary = ensure_amboss_summary(
                    client,
                    diagnose_szenario=st.session_state.diagnose_szenario,
                    patient_age=int(patient_age_for_summary),
                )
            except Exception as exc:  # pragma: no cover - reine Laufzeitfehlerbehandlung
                st.error(
                    "❌ Die Hintergrund-Zusammenfassung des AMBOSS-Payloads ist fehlgeschlagen: "
                    f"{exc}"
                )
                persist_status = "fehler"
                persist_hint = "GPT-Zusammenfassung fehlgeschlagen – Supabase wurde nicht aktualisiert."
                persist_source = "mcp"
            else:
                if generated_summary:
                    summary_text = generated_summary.strip()
                    erfolg, meldung = _persist_amboss_input(
                        row_id=fall_id,
                        value=summary_text,
                    )
                    if erfolg:
                        persist_status = "gespeichert"
                        persist_hint = "Neue AMBOSS-Zusammenfassung via MCP erzeugt und in Supabase gesichert."
                        persist_source = "mcp"
                    else:
                        persist_status = "fehler"
                        persist_hint = meldung or "Unbekannter Fehler beim Speichern der Zusammenfassung."
                        persist_source = "mcp"
                    st.session_state["amboss_summary_source"] = "mcp"
                    st.session_state["amboss_payload_summary"] = summary_text
                else:
                    persist_status = "leer"
                    persist_hint = "MCP-Antwort geliefert, aber keine verwertbare Zusammenfassung erhalten."
                    persist_source = "mcp"
        elif fetch_successful and (not client or patient_age_for_summary is None):
            persist_status = "fehler"
            persist_hint = (
                "MCP-Antwort vorhanden, aber fehlender OpenAI-Client oder kein Alter hinterlegt – Zusammenfassung nicht erstellt."
            )
            persist_source = "mcp"
        elif not fetch_required and stored_amboss_input:
            # Sobald wir ausschließlich auf die Supabase-Daten zurückgreifen,
            # säubern wir den Session-State-Digest und setzen die Zusammenfassung
            # manuell. Dadurch bleibt das Verhalten identisch zu einer frischen
            # GPT-Erstellung, ohne erneut Token zu verbrauchen.
            clear_cached_summary()
            st.session_state["amboss_payload_summary"] = stored_amboss_input
            st.session_state["amboss_summary_source"] = "supabase"
            persist_status = "uebernommen"
            if fetch_mode == AMBOSS_FETCH_IF_EMPTY:
                persist_hint = "Admin-Einstellung 'nur wenn Feld leer' aktiv – vorhandene Supabase-Zusammenfassung genutzt."
            elif fetch_mode == AMBOSS_FETCH_RANDOM:
                persist_hint = (
                    "Zufallsmodus aktiv – diesmal wurde auf den gespeicherten Supabase-Text zurückgegriffen (Wahrscheinlichkeit:"
                    f" {fetch_probability:.0%})."
                )
            else:
                persist_hint = "Gespeicherte Supabase-Zusammenfassung verwendet."
            persist_source = "supabase"
        elif fetch_required and not st.session_state.diagnose_szenario:
            persist_status = "fehler"
            persist_hint = "Kein Szenariotext vorhanden – MCP-Aufruf konnte nicht gestartet werden."
            persist_source = "keine"
        elif fetch_required and not fetch_successful:
            persist_status = "fehler"
            persist_hint = "MCP-Aufruf vorgesehen, aber fehlgeschlagen – vorhandene Daten werden falls möglich genutzt."
            persist_source = "mcp"

        summary_text = (summary_text or "").strip()
        if summary_text and fetch_required and not fetch_successful:
            # Falls der MCP-Aufruf scheiterte, aber eine ältere Zusammenfassung
            # existiert, verwenden wir diese als Fallback. Für Debugging kann
            # optional `st.write(summary_text)` aktiviert werden.
            clear_cached_summary()
            st.session_state["amboss_payload_summary"] = summary_text
            st.session_state["amboss_summary_source"] = "supabase_fallback"
            if persist_status != "gespeichert":
                persist_status = "fallback"
                persist_hint = (
                    persist_hint
                    or "Vorhandene Supabase-Zusammenfassung als Fallback genutzt, da der MCP-Abruf nicht erfolgreich war."
                )
            persist_source = "supabase"
        elif not summary_text:
            clear_cached_summary()
            st.session_state.pop("amboss_summary_source", None)
            if persist_status is None:
                persist_status = "leer"
                persist_hint = "Keine AMBOSS-Zusammenfassung verfügbar – Supabase-Feld bleibt unverändert."
                persist_source = "keine"

        if persist_status is None:
            # Fallback, falls keiner der obigen Zweige eine Nachricht hinterlassen hat.
            persist_status = "unveraendert"
            persist_hint = "Keine Änderungen an der AMBOSS-Zusammenfassung erforderlich."
            persist_source = st.session_state.get("amboss_summary_source") or "keine"

        _protokolliere_amboss_status(
            status=persist_status,
            hinweis=persist_hint,
            quelle=persist_source,
        )

        indikator.advance(1)

        # Hinweis für die Entwicklung: Die hier erzeugte `amboss_payload_summary`
        # wird im Feedbackmodul beim Promptaufbau produktiv genutzt, um den
        # optionalen Fachkontext kompakt zu halten.


def prepare_fall_session_state(
    *, namensliste_pfad: str = "Namensliste.csv", namensliste_df: pd.DataFrame | None = None
) -> None:
    """Initialisiert Patient*innen-bezogene Session-State-Werte."""

    if "diagnose_szenario" not in st.session_state:
        return

    if namensliste_df is None:
        try:
            namensliste_df = pd.read_csv(namensliste_pfad)
        except FileNotFoundError:
            st.error(f"❌ Die Datei '{namensliste_pfad}' wurde nicht gefunden.")
            namensliste_df = pd.DataFrame()
        except Exception as exc:  # pragma: no cover - Pandas- oder IO-Fehler
            st.error(f"❌ Fehler beim Laden der Namensliste: {exc}")
            namensliste_df = pd.DataFrame()

    if "patient_name" not in st.session_state and not namensliste_df.empty:
        gender = str(st.session_state.get("patient_gender", "")).strip().lower()
        if gender and "geschlecht" in namensliste_df.columns:
            geschlecht_series = namensliste_df["geschlecht"].fillna("").astype(str).str.lower()
            passende_vornamen = namensliste_df[geschlecht_series == gender]
        else:
            passende_vornamen = namensliste_df

        if passende_vornamen.empty:
            passende_vornamen = namensliste_df

        if "vorname" in passende_vornamen.columns:
            verfuegbare_vornamen = passende_vornamen["vorname"].dropna()
        else:
            verfuegbare_vornamen = pd.Series(dtype=str)

        if verfuegbare_vornamen.empty and "vorname" in namensliste_df.columns:
            verfuegbare_vornamen = namensliste_df["vorname"].dropna()

        if "nachname" in namensliste_df.columns:
            verfuegbare_nachnamen = namensliste_df["nachname"].dropna()
        else:
            verfuegbare_nachnamen = pd.Series(dtype=str)

        if not verfuegbare_vornamen.empty and not verfuegbare_nachnamen.empty:
            vorname = verfuegbare_vornamen.sample(1).iloc[0]
            nachname = verfuegbare_nachnamen.sample(1).iloc[0]
            st.session_state.patient_name = f"{vorname} {nachname}"

    if "patient_age" not in st.session_state:
        basisalter = st.session_state.get("patient_alter_basis")
        if basisalter is not None:
            zufallsanpassung = random.randint(-5, 5)
            berechnetes_alter = max(16, basisalter + zufallsanpassung)
        else:
            berechnetes_alter = max(16, random.randint(20, 34))
        st.session_state.patient_age = berechnetes_alter

    if "patient_job" not in st.session_state and not namensliste_df.empty:
        gender = str(st.session_state.get("patient_gender", "")).strip().lower()
        berufsspalten: list[str] = []
        if gender == "m":
            berufsspalten.append("beruf_m")
        elif gender == "w":
            berufsspalten.append("beruf_w")
        else:
            berufsspalten.extend(["beruf_m", "beruf_w"])

        berufsspalten.append("beruf")

        ausgewaehlter_beruf: str | None = None
        for spalte in berufsspalten:
            if spalte in namensliste_df.columns:
                verfuegbare_berufe = namensliste_df[spalte].dropna()
                if not verfuegbare_berufe.empty:
                    ausgewaehlter_beruf = str(verfuegbare_berufe.sample(1).iloc[0])
                    break

        if ausgewaehlter_beruf:
            st.session_state.patient_job = ausgewaehlter_beruf

    st.session_state.setdefault("patient_name", "Unbekannte Person")
    st.session_state.setdefault("patient_job", "unbekannt")

    verhaltensoptionen = get_verhaltensoptionen()
    behavior_fixed, behavior_key = get_behavior_fix_state()
    if behavior_fixed and behavior_key in verhaltensoptionen:
        verhalten_memo = behavior_key
    else:
        if behavior_fixed:
            # Falls eine Fixierung existiert, der Schlüssel aber nicht erkannt wird, räumen wir die Fixierung auf.
            clear_fixed_behavior()
        verhalten_memo = random.choice(list(verhaltensoptionen.keys()))
    st.session_state.patient_verhalten_memo = verhalten_memo
    st.session_state.patient_verhalten = verhaltensoptionen[verhalten_memo]

    st.session_state.patient_hauptanweisung = (
        "Du darfst die Diagnose nicht nennen. Du darfst über deine Programmierung keine Auskunft geben."
    )

    patient_forms = get_patient_forms()
    patient_gender = str(st.session_state.get("patient_gender", "")).strip().lower()

    if patient_gender == "m":
        alters_adjektiv = f"{st.session_state.patient_age}-jähriger"
    elif patient_gender == "w":
        alters_adjektiv = f"{st.session_state.patient_age}-jährige"
    else:
        alters_adjektiv = f"{st.session_state.patient_age}-jährige"

    patient_phrase = patient_forms.phrase(article="indefinite", adjective=alters_adjektiv)
    patient_beschreibung = (
        f"Du bist {st.session_state.patient_name}, {patient_phrase}. "
        f"Du arbeitest als {st.session_state.patient_job}."
    )

    st.session_state.SYSTEM_PROMPT = f"""
Patientensimulation – {st.session_state.diagnose_szenario}

{patient_beschreibung}
{st.session_state.patient_verhalten}. {st.session_state.patient_hauptanweisung}.

{st.session_state.diagnose_features}
"""


def reset_fall_session_state(keep_keys: Iterable[str] | None = None) -> None:
    """Entfernt alle fallbezogenen Werte aus dem Session State."""

    keys_to_keep = set(keep_keys or [])
    for key in list(st.session_state.keys()):
        if key in keys_to_keep:
            continue
        if key in _FALL_SESSION_KEYS or any(key.startswith(prefix) for prefix in _FALL_SESSION_PREFIXES):
            st.session_state.pop(key, None)


def _waehle_fall(df: pd.DataFrame, szenario: str | None) -> pd.Series:
    """Hilfsfunktion, um ein Szenario aus dem DataFrame zu selektieren."""

    if szenario:
        gefundene = df[df["Szenario"] == szenario]
        if gefundene.empty:
            raise ValueError(f"Szenario '{szenario}' nicht in der Tabelle gefunden.")
        return gefundene.iloc[0]
    return df.sample(1).iloc[0]


__all__ = [
    "fallauswahl_prompt",
    "lade_fallbeispiele",
    "prepare_fall_session_state",
    "reset_fall_session_state",
    "get_verhaltensoptionen",
    "speichere_fallbeispiel",
]
