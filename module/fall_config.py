"""Persistente Speicherung des Fall-Fixierungszustands."""

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
]

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_CONFIG_PATH = _DATA_DIR / "fall_config.json"

_LOCK = Lock()
_DEFAULT_CONFIG: Dict[str, Any] = {"fixed": False, "scenario": "", "fixed_at": ""}


def _load_config() -> Dict[str, Any]:
    """Liest die gespeicherte Konfiguration ein."""

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
        _save_config(dict(_DEFAULT_CONFIG))
        return dict(_DEFAULT_CONFIG)
    if not isinstance(data, dict):
        _save_config(dict(_DEFAULT_CONFIG))
        return dict(_DEFAULT_CONFIG)
    fixed = bool(data.get("fixed", False))
    scenario = str(data.get("scenario", ""))
    fixed_at = str(data.get("fixed_at", ""))
    return {"fixed": fixed, "scenario": scenario, "fixed_at": fixed_at}


def _save_config(data: Dict[str, Any]) -> None:
    """Speichert die Konfiguration sicher."""

    serializable = {
        "fixed": bool(data.get("fixed", False)),
        "scenario": str(data.get("scenario", "")),
        "fixed_at": str(data.get("fixed_at", "")),
    }
    with _LOCK:
        try:
            _CONFIG_PATH.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass


def get_fall_fix_state() -> Tuple[bool, str]:
    """Gibt zurück, ob ein Szenario fixiert ist und welches Szenario gesetzt wurde."""

    data = _load_config()
    if data.get("fixed"):
        # Hinweis: Wir parsen das gespeicherte Zeitstempel-ISO-Format und prüfen, ob die 2h-Frist bereits
        # abgelaufen ist. Sollte das Format unerwartet sein, wird die Fixierung sicherheitshalber aufgehoben.
        fixed_at_raw = str(data.get("fixed_at", ""))
        try:
            fixed_at = datetime.fromisoformat(fixed_at_raw)
            # Wir stellen sicher, dass der Zeitstempel Zeitzoneninformationen enthält, um UTC-basierte Vergleiche
            # zu ermöglichen. Für Debugging-Zwecke kann bei Bedarf `print(fixed_at)` aktiviert werden.
            if fixed_at.tzinfo is None:
                fixed_at = fixed_at.replace(tzinfo=timezone.utc)
        except ValueError:
            fixed_at = None

        now = datetime.now(timezone.utc)
        if not fixed_at or now - fixed_at >= timedelta(hours=2):
            # Automatisches Aufheben nach Ablauf der Frist. Für Debugging lässt sich hier ein Logging-Hook
            # ergänzen, falls ein detailliertes Monitoring erforderlich ist.
            _save_config(dict(_DEFAULT_CONFIG))
            return False, ""

    return bool(data.get("fixed", False)), str(data.get("scenario", ""))


def set_fixed_scenario(szenario: str) -> None:
    """Aktiviert die Fall-Fixierung für das angegebene Szenario."""

    scenario_value = str(szenario).strip()
    # Wir speichern zusätzlich einen UTC-Zeitstempel, damit die automatische Aufhebung nach 2 Stunden
    # zuverlässig ausgelöst werden kann. Für Analysen kann dieser Wert aus der JSON-Datei ausgelesen werden.
    _save_config(
        {
            "fixed": True,
            "scenario": scenario_value,
            "fixed_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def clear_fixed_scenario() -> None:
    """Deaktiviert die Fall-Fixierung und entfernt das gespeicherte Szenario."""

    _save_config(dict(_DEFAULT_CONFIG))
