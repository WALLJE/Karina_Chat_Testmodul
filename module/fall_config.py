"""Persistente Speicherung der Fixierungen für Szenario und Verhalten."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Tuple

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
    "get_config_file_status",
]

# Der Datenordner liegt eine Ebene über dem Modulverzeichnis, damit alle Komponenten
# auf denselben Speicherort zugreifen können. Sollte der Pfad nicht existieren, wird er
# automatisch angelegt.
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_CONFIG_PATH = _DATA_DIR / "fall_config.json"

# Die Lock-Instanz stellt sicher, dass Lese- und Schreibzugriffe threadsicher erfolgen.
_LOCK = Lock()
_DEFAULT_CONFIG: Dict[str, Any] = {
    "fixed": False,
    "scenario": "",
    "fixed_at": "",
    "behavior_fixed": False,
    "behavior": "",
    "behavior_fixed_at": "",
    # Persistente Einstellung für den kombinierten ChatGPT+AMBOSS-Modus.
    # Die Werte spiegeln exakt das Schema der übrigen Fixierungen wider, damit
    # dieselben Hilfsfunktionen genutzt werden können.
    "feedback_mode_fixed": False,
    "feedback_mode": "",
    "feedback_mode_fixed_at": "",
}


def _normalize_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Stellt sicher, dass alle erwarteten Schlüssel gesetzt und typisiert sind."""

    normalized = dict(_DEFAULT_CONFIG)
    for key in normalized:
        value = data.get(key, normalized[key])
        if key in {"fixed", "behavior_fixed", "feedback_mode_fixed"}:
            normalized[key] = bool(value)
        else:
            normalized[key] = str(value) if isinstance(normalized[key], str) else value
    return normalized


def _load_config() -> Dict[str, Any]:
    """Liest die Konfiguration aus der JSON-Datei ein."""

    with _LOCK:
        if not _CONFIG_PATH.exists():
            return dict(_DEFAULT_CONFIG)
        try:
            raw = _CONFIG_PATH.read_text(encoding="utf-8")
        except OSError:
            return dict(_DEFAULT_CONFIG)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Falls die Datei korrupt ist, setzen wir sie auf den Standard zurück, damit
        # die Anwendung nicht in einem ungültigen Zustand verbleibt.
        _save_config(dict(_DEFAULT_CONFIG))
        return dict(_DEFAULT_CONFIG)
    if not isinstance(data, dict):
        _save_config(dict(_DEFAULT_CONFIG))
        return dict(_DEFAULT_CONFIG)
    return _normalize_config(data)


def _save_config(data: Dict[str, Any]) -> None:
    """Schreibt die Konfiguration threadsicher in die JSON-Datei."""

    serializable = _normalize_config(data)
    with _LOCK:
        try:
            _CONFIG_PATH.write_text(
                json.dumps(serializable, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            # Für Debugging kann hier optional ein Logging aktiviert werden, das aufzeigt,
            # weshalb ein Speichern fehlgeschlagen ist.
            pass


def _evaluate_fix_state(
    data: Dict[str, Any],
    *,
    fixed_key: str,
    value_key: str,
    timestamp_key: str,
) -> Tuple[bool, str]:
    """Prüft Ablaufzeiten und räumt ungültige Fixierungen automatisch auf."""

    if not data.get(fixed_key):
        return False, ""

    value_raw = str(data.get(value_key, ""))
    timestamp_raw = str(data.get(timestamp_key, ""))

    try:
        fixed_at = datetime.fromisoformat(timestamp_raw)
        if fixed_at.tzinfo is None:
            fixed_at = fixed_at.replace(tzinfo=timezone.utc)
    except ValueError:
        fixed_at = None

    now = datetime.now(timezone.utc)
    if not fixed_at or now - fixed_at >= timedelta(hours=2) or not value_raw:
        # Optionaler Debug-Hinweis: Bei Bedarf kann hier Logging aktiviert werden, das den Ablaufgrund protokolliert.
        data.update({fixed_key: False, value_key: "", timestamp_key: ""})
        _save_config(data)
        return False, ""

    return True, value_raw


def get_fall_fix_state() -> Tuple[bool, str]:
    """Gibt zurück, ob ein Szenario fixiert ist und welches Szenario gesetzt wurde."""

    data = _load_config()
    return _evaluate_fix_state(data, fixed_key="fixed", value_key="scenario", timestamp_key="fixed_at")


def set_fixed_scenario(szenario: str) -> None:
    """Aktiviert die Fall-Fixierung für das angegebene Szenario."""

    scenario_value = str(szenario).strip()
    config = _load_config()
    config.update(
        {
            "fixed": True,
            "scenario": scenario_value,
            "fixed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    # Für Debugging kann hier optional ein Print-Statement aktiviert werden, um den Zeitpunkt der Fixierung zu prüfen.
    _save_config(config)


def clear_fixed_scenario() -> None:
    """Deaktiviert die Fall-Fixierung und entfernt das gespeicherte Szenario."""

    config = _load_config()
    config.update({"fixed": False, "scenario": "", "fixed_at": ""})
    _save_config(config)


def get_behavior_fix_state() -> Tuple[bool, str]:
    """Gibt zurück, ob ein Verhalten fixiert ist und welches Kennwort gesetzt wurde."""

    data = _load_config()
    return _evaluate_fix_state(
        data,
        fixed_key="behavior_fixed",
        value_key="behavior",
        timestamp_key="behavior_fixed_at",
    )


def set_fixed_behavior(behavior_key: str) -> None:
    """Aktiviert die Fixierung für das übergebene Verhalten."""

    behavior_value = str(behavior_key).strip()
    config = _load_config()
    config.update(
        {
            "behavior_fixed": True,
            "behavior": behavior_value,
            "behavior_fixed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    # Für Fehlersuche kann hier ein Logging ergänzt werden, das den gesetzten Verhaltensschlüssel dokumentiert.
    _save_config(config)


def clear_fixed_behavior() -> None:
    """Deaktiviert die Verhaltens-Fixierung und setzt die Werte zurück."""

    config = _load_config()
    config.update({"behavior_fixed": False, "behavior": "", "behavior_fixed_at": ""})
    _save_config(config)


def get_feedback_mode_fix_state() -> Tuple[bool, str]:
    """Liefert, ob eine persistente Feedback-Mode-Fixierung aktiv ist."""

    data = _load_config()
    active, value = _evaluate_fix_state(
        data,
        fixed_key="feedback_mode_fixed",
        value_key="feedback_mode",
        timestamp_key="feedback_mode_fixed_at",
    )
    return active, value


def get_feedback_mode_fix_info() -> Tuple[bool, str, timedelta]:
    """Gibt zusätzliche Details zur verbleibenden Laufzeit der Fixierung zurück."""

    data = _load_config()
    active, value = _evaluate_fix_state(
        data,
        fixed_key="feedback_mode_fixed",
        value_key="feedback_mode",
        timestamp_key="feedback_mode_fixed_at",
    )
    if not active:
        return False, "", timedelta(0)

    timestamp_raw = str(data.get("feedback_mode_fixed_at", ""))
    try:
        fixed_at = datetime.fromisoformat(timestamp_raw)
        if fixed_at.tzinfo is None:
            fixed_at = fixed_at.replace(tzinfo=timezone.utc)
    except ValueError:
        fixed_at = datetime.now(timezone.utc) - timedelta(hours=2)

    now = datetime.now(timezone.utc)
    remaining = (fixed_at + timedelta(hours=2)) - now
    if remaining < timedelta(0):
        remaining = timedelta(0)
    return True, value, remaining


def set_feedback_mode_fix(mode: str) -> None:
    """Persistiert den gewünschten Feedback-Modus für zwei Stunden."""

    mode_value = str(mode).strip()
    config = _load_config()
    config.update(
        {
            "feedback_mode_fixed": True,
            "feedback_mode": mode_value,
            "feedback_mode_fixed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    # Für Fehlersuche kann hier optional ein Logging ergänzt werden, das festhält,
    # wann die Persistierung gesetzt wurde.
    _save_config(config)


def clear_feedback_mode_fix() -> None:
    """Entfernt die persistente Feedback-Mode-Fixierung."""

    config = _load_config()
    config.update(
        {
            "feedback_mode_fixed": False,
            "feedback_mode": "",
            "feedback_mode_fixed_at": "",
        }
    )
    _save_config(config)


def get_config_file_status() -> tuple[bool, str]:
    """Prüft, ob die JSON-Konfigurationsdatei vorhanden und lesbar ist."""

    # Wir liefern zwecks Anzeige im Adminbereich einen booleschen Status sowie
    # eine erklärende Nachricht zurück. Dadurch können Admins schnell erkennen,
    # ob die Fixierungsinformationen aus ``fall_config.json`` zuverlässig
    # geladen werden. Für detaillierte Fehlersuche lässt sich die Nachricht
    # bei Bedarf im UI erweitern oder loggen.
    if not _CONFIG_PATH.exists():
        return False, "Konfigurationsdatei wurde nicht erstellt - keine Fixierung aktiv."

    try:
        raw = _CONFIG_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"Die Konfigurationsdatei konnte nicht gelesen werden: {exc}"

    if not raw.strip():
        # Eine leere Datei behandeln wir als Hinweis darauf, dass noch keine
        # Fixierungen gespeichert wurden. Technisch ist das in Ordnung, daher
        # liefern wir einen Erfolgshinweis mit zusätzlicher Erläuterung.
        return True, "Die Konfigurationsdatei ist leer, kann aber gelesen werden."

    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        return False, f"Die Konfigurationsdatei enthält ungültiges JSON: {exc}"

    return True, "Die Konfigurationsdatei ist vorhanden und gültig."
