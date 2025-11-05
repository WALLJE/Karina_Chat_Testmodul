"""Persistente Speicherung der Fixierungen über eine Supabase-Tabelle."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import streamlit as st
from supabase import Client, create_client

__all__ = [
    "get_fall_fix_state",
    "set_fixed_scenario",
    "clear_fixed_scenario",
    "get_behavior_fix_state",
    "set_fixed_behavior",
    "clear_fixed_behavior",
    "get_feedback_mode_fix_state",
    "get_feedback_mode_fix_info",
    "set_feedback_mode_fix",
    "clear_feedback_mode_fix",
    "get_amboss_fetch_preferences",
    "set_amboss_fetch_mode",
    "set_amboss_random_probability",
    "get_all_persisted_parameters",
    "AMBOSS_FETCH_ALWAYS",
    "AMBOSS_FETCH_IF_EMPTY",
    "AMBOSS_FETCH_RANDOM",
]

# Name der Supabase-Tabelle, in der alle Fixierungen persistiert werden.
_TABLE_NAME = "fall_persistenzen"

# Gültige Kennwörter für den AMBOSS-Abrufmodus. Die Werte werden eins-zu-eins in
# der Datenbank abgelegt, sodass keine weiteren Transformationen nötig sind.
AMBOSS_FETCH_ALWAYS = "always"
AMBOSS_FETCH_IF_EMPTY = "if_empty"
AMBOSS_FETCH_RANDOM = "random"

# Standardwerte für den AMBOSS-Zufallsmodus. Sie greifen, wenn noch kein Eintrag
# in Supabase existiert oder ein Datensatz unvollständig ist.
_DEFAULT_AMBOSS_MODE = AMBOSS_FETCH_RANDOM
_DEFAULT_AMBOSS_RANDOM_PROBABILITY = 0.2

# Interner Cache. Er wird lazy geladen, damit beim Start der Anwendung sofort die
# Datenbankwerte verfügbar sind, aber nicht bei jedem Zugriff ein Netzwerk-Call
# ausgelöst wird. Nach jedem Schreibvorgang wird er invalidiert.
_STATE_CACHE: Dict[str, Dict[str, Any]] | None = None


def _get_supabase_client() -> Client:
    """Erstellt einen Supabase-Client anhand der Streamlit-Secrets."""

    supabase_config = st.secrets.get("supabase")
    if not supabase_config:
        raise RuntimeError(
            "Supabase-Konfiguration fehlt in st.secrets. Bitte prüfe den Abschnitt 'supabase' im Streamlit-Backend."
        )

    try:
        url = supabase_config["url"]
        key = supabase_config["key"]
    except KeyError as exc:  # pragma: no cover - defensive Absicherung
        raise RuntimeError(
            "Supabase-Zugangsdaten sind unvollständig. Erwartet werden 'url' und 'key'."
        ) from exc

    try:
        return create_client(url, key)
    except Exception as exc:  # pragma: no cover - defensive Absicherung
        raise RuntimeError(
            "Supabase-Verbindung konnte nicht hergestellt werden. Hinweise siehe Kommentare im Code."
        ) from exc


def _refresh_cache() -> Dict[str, Dict[str, Any]]:
    """Lädt sämtliche Fixierungen aus Supabase und gibt sie als Wörterbuch zurück."""

    client = _get_supabase_client()
    try:
        response = client.table(_TABLE_NAME).select("*").execute()
    except Exception as exc:  # pragma: no cover - defensive Absicherung
        raise RuntimeError(
            "Abruf der Tabelle 'fall_persistenzen' fehlgeschlagen."
        ) from exc

    if getattr(response, "error", None):
        raise RuntimeError(
            f"Supabase meldet einen Fehler beim Laden der Fixierungen: {response.error}"
        )

    rows = response.data or []
    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = row.get("fix_key")
        if not isinstance(key, str):
            continue
        key = key.strip()
        if not key:
            continue
        # Bei doppelten Einträgen behalten wir den zuletzt aktualisierten Datensatz.
        existing = result.get(key)
        if existing:
            existing_updated = existing.get("updated_at")
            row_updated = row.get("updated_at")
            if existing_updated and row_updated and str(row_updated) < str(existing_updated):
                continue
        result[key] = dict(row)
    return result


def _ensure_cache() -> Dict[str, Dict[str, Any]]:
    """Stellt sicher, dass der Cache gefüllt ist, und liefert ihn zurück."""

    global _STATE_CACHE
    if _STATE_CACHE is None:
        _STATE_CACHE = _refresh_cache()
    return _STATE_CACHE


def _invalidate_cache() -> None:
    """Leert den Cache nach Schreiboperationen."""

    global _STATE_CACHE
    _STATE_CACHE = None


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Konvertiert ISO-Strings oder datetime-Objekte in UTC-normalisierte Werte."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _sanitize_fetch_mode(mode: str) -> str:
    """Säubert beliebige Eingaben und reduziert sie auf bekannte Abrufmodi."""

    mode_clean = str(mode).strip().lower()
    if mode_clean not in {AMBOSS_FETCH_ALWAYS, AMBOSS_FETCH_IF_EMPTY, AMBOSS_FETCH_RANDOM}:
        return AMBOSS_FETCH_RANDOM
    return mode_clean


def _sanitize_probability(probability: Any) -> float:
    """Schneidet Wahrscheinlichkeiten auf den Bereich 0.0 bis 1.0 zu."""

    try:
        value = float(probability)
    except (TypeError, ValueError):
        value = _DEFAULT_AMBOSS_RANDOM_PROBABILITY
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _persist_fixation(
    fix_key: str,
    *,
    is_active: bool,
    value_text: str = "",
    value_number: Optional[float] = None,
) -> None:
    """Schreibt eine Fixierung in Supabase und aktualisiert anschließend den Cache."""

    client = _get_supabase_client()
    payload: Dict[str, Any] = {
        "fix_key": fix_key,
        "is_active": is_active,
        "value_text": value_text,
        "value_number": value_number,
        "fixed_at": datetime.now(timezone.utc).isoformat() if is_active else None,
        "expires_at": None,
    }

    existing = _ensure_cache().get(fix_key)
    try:
        if existing:
            response = (
                client.table(_TABLE_NAME)
                .update(payload)
                .eq("fix_key", fix_key)
                .execute()
            )
        else:
            response = client.table(_TABLE_NAME).insert(payload).execute()
    except Exception as exc:  # pragma: no cover - defensive Absicherung
        raise RuntimeError(
            f"Schreiben der Fixierung '{fix_key}' in Supabase fehlgeschlagen."
        ) from exc

    if getattr(response, "error", None):
        raise RuntimeError(
            f"Supabase meldet beim Persistieren von '{fix_key}' einen Fehler: {response.error}"
        )

    _invalidate_cache()


def _get_entry(fix_key: str) -> Dict[str, Any]:
    """Liefert den aktuellen Datensatz einer Fixierung oder ein leeres Dict."""

    data = _ensure_cache()
    entry = data.get(fix_key)
    if entry is None:
        return {}
    return dict(entry)


def get_fall_fix_state() -> Tuple[bool, str]:
    """Gibt zurück, ob ein Szenario fixiert ist und welches Szenario gesetzt wurde."""

    entry = _get_entry("scenario")
    if not entry or not entry.get("is_active"):
        return False, ""
    value = str(entry.get("value_text", "")).strip()
    return bool(value), value


def set_fixed_scenario(szenario: str) -> None:
    """Aktiviert die Fall-Fixierung für das angegebene Szenario."""

    scenario_value = str(szenario).strip()
    if not scenario_value:
        raise ValueError("Das zu fixierende Szenario darf nicht leer sein.")
    _persist_fixation("scenario", is_active=True, value_text=scenario_value)


def clear_fixed_scenario() -> None:
    """Deaktiviert die Fall-Fixierung und entfernt das gespeicherte Szenario."""

    _persist_fixation("scenario", is_active=False, value_text="", value_number=None)


def get_behavior_fix_state() -> Tuple[bool, str]:
    """Gibt zurück, ob ein Verhalten fixiert ist und welches Kennwort gesetzt wurde."""

    entry = _get_entry("behavior")
    if not entry or not entry.get("is_active"):
        return False, ""
    value = str(entry.get("value_text", "")).strip()
    return bool(value), value


def set_fixed_behavior(behavior_key: str) -> None:
    """Aktiviert die Fixierung für das übergebene Verhalten."""

    behavior_value = str(behavior_key).strip()
    if not behavior_value:
        raise ValueError("Der Verhaltensschlüssel darf nicht leer sein.")
    _persist_fixation("behavior", is_active=True, value_text=behavior_value)


def clear_fixed_behavior() -> None:
    """Deaktiviert die Verhaltens-Fixierung und setzt die Werte zurück."""

    _persist_fixation("behavior", is_active=False, value_text="", value_number=None)


def get_feedback_mode_fix_state() -> Tuple[bool, str]:
    """Liefert, ob eine persistente Feedback-Mode-Fixierung aktiv ist."""

    entry = _get_entry("feedback_mode")
    if not entry or not entry.get("is_active"):
        return False, ""
    value = str(entry.get("value_text", "")).strip()
    return bool(value), value


def get_feedback_mode_fix_info() -> Tuple[bool, str, Optional[datetime]]:
    """Gibt zusätzliche Details zur zuletzt gesetzten Fixierung zurück."""

    active, value = get_feedback_mode_fix_state()
    if not active:
        return False, "", None
    entry = _get_entry("feedback_mode")
    timestamp = _parse_timestamp(entry.get("fixed_at"))
    return True, value, timestamp


def set_feedback_mode_fix(mode: str) -> None:
    """Persistiert den gewünschten Feedback-Modus dauerhaft."""

    mode_value = str(mode).strip()
    if not mode_value:
        raise ValueError("Der Feedback-Modus darf nicht leer sein.")
    _persist_fixation("feedback_mode", is_active=True, value_text=mode_value)


def clear_feedback_mode_fix() -> None:
    """Entfernt die persistente Feedback-Mode-Fixierung."""

    _persist_fixation("feedback_mode", is_active=False, value_text="", value_number=None)


def get_amboss_fetch_preferences() -> Tuple[str, float]:
    """Liefert den persistent gespeicherten Abrufmodus und die Zufallswahrscheinlichkeit."""

    entry = _get_entry("amboss_mode")
    if not entry:
        return _DEFAULT_AMBOSS_MODE, _DEFAULT_AMBOSS_RANDOM_PROBABILITY

    mode = _sanitize_fetch_mode(entry.get("value_text", _DEFAULT_AMBOSS_MODE))
    probability = _sanitize_probability(entry.get("value_number", _DEFAULT_AMBOSS_RANDOM_PROBABILITY))
    return mode, probability


def set_amboss_fetch_mode(mode: str) -> None:
    """Persistiert den gewünschten Abrufmodus für den AMBOSS-MCP."""

    sanitized_mode = _sanitize_fetch_mode(mode)
    _, probability = get_amboss_fetch_preferences()
    _persist_fixation(
        "amboss_mode",
        is_active=True,
        value_text=sanitized_mode,
        value_number=probability,
    )


def set_amboss_random_probability(probability: float) -> None:
    """Speichert die gewünschte Zufallswahrscheinlichkeit dauerhaft."""

    mode, _ = get_amboss_fetch_preferences()
    sanitized_probability = _sanitize_probability(probability)
    _persist_fixation(
        "amboss_mode",
        is_active=True,
        value_text=mode,
        value_number=sanitized_probability,
    )


def get_all_persisted_parameters() -> Dict[str, Dict[str, Any]]:
    """Liefert eine lesbare Übersicht aller aktuell gespeicherten Parameter."""

    data = _ensure_cache()
    overview: Dict[str, Dict[str, Any]] = {}
    for key, entry in data.items():
        overview[key] = {
            "aktiv": bool(entry.get("is_active")),
            "wert_text": entry.get("value_text", ""),
            "wert_nummer": entry.get("value_number"),
            "gesetzt_am": entry.get("fixed_at"),
            "letzte_aktualisierung": entry.get("updated_at"),
        }
    return overview
