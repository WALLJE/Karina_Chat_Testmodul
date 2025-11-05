"""Vorverarbeitung der AMBOSS-Nutzlast für die Feedback-Generierung."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

import streamlit as st

from module.token_counter import add_usage, init_token_counters

# Session-State-Schlüssel, unter denen die verdichteten Informationen abgelegt werden.
_SUMMARY_KEY = "amboss_payload_summary"
_DIGEST_KEY = "amboss_payload_summary_digest"


def _serialize_payload(payload: Any) -> str:
    """Wandelt die ursprüngliche AMBOSS-Antwort in einen stabilen JSON-String um."""

    try:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    except TypeError:
        # Sollte das Objekt nicht JSON-serialisierbar sein, greifen wir auf ``str``
        # zurück. Für detailliertes Debugging kann hier ein ``st.write`` ergänzt
        # werden, der den problematischen Datentyp anzeigt.
        return str(payload)


def _build_digest(serialized_payload: str, diagnose_szenario: str, patient_age: int) -> str:
    """Erstellt einen Hash, um identische Nutzlasten wiederzuerkennen."""

    hasher = hashlib.sha256()
    hasher.update(serialized_payload.encode("utf-8"))
    hasher.update(str(diagnose_szenario).encode("utf-8"))
    hasher.update(str(patient_age).encode("utf-8"))
    return hasher.hexdigest()


def clear_cached_summary() -> None:
    """Entfernt gespeicherte Zusammenfassungen aus dem Session State."""

    st.session_state.pop(_SUMMARY_KEY, None)
    st.session_state.pop(_DIGEST_KEY, None)


def get_cached_summary() -> Optional[str]:
    """Liefert die aktuell zwischengespeicherte Zusammenfassung, falls vorhanden."""

    return st.session_state.get(_SUMMARY_KEY)


def ensure_amboss_summary(
    client,
    *,
    diagnose_szenario: str,
    patient_age: int,
) -> Optional[str]:
    """Erstellt bei Bedarf eine kompakte Zusammenfassung des AMBOSS-Payloads."""

    payload = st.session_state.get("amboss_result")
    if not payload:
        clear_cached_summary()
        return None

    serialized = _serialize_payload(payload)
    digest = _build_digest(serialized, diagnose_szenario, patient_age)

    cached_digest = st.session_state.get(_DIGEST_KEY)
    if cached_digest == digest:
        return st.session_state.get(_SUMMARY_KEY)

    prompt = (
        "Du bist medizinische*r Content-Kurator*in. Verdichte die folgenden AMBOSS-Daten "
        "für einen digitalen Prüfer. Konzentriere dich auf anamnestische, diagnostische "
        "und therapeutische Kernaussagen sowie auf die wichtigsten Differentialdiagnosen "
        "mit ihrer Abgrenzung zur Hauptdiagnose."
        "\n\n"
        f"Fallkontext Szenario = {diagnose_szenario}. Nur zur Information, nicht in Antwort übernehmen: Alter = {patient_age} Jahre."
        "\n\n"
        "Erstelle vier kurze Abschnitte mit fett formatierten Überschriften:"
        "\n1. Anamnese & Klinik"
        "\n2. Diagnostik"
        "\n3. Therapie"
        "\n4. Differentialdiagnosen"
        "\nNutze Stichpunkte oder komprimierte Sätze, "
        "ohne inhaltliche Details zu streichen."
        "\n\nAMBOSS-JSON:"
        f"\n{serialized}"
    )

    init_token_counters()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    add_usage(
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens,
    )

    summary = response.choices[0].message.content.strip()
    st.session_state[_SUMMARY_KEY] = summary
    st.session_state[_DIGEST_KEY] = digest
    return summary


__all__ = [
    "clear_cached_summary",
    "ensure_amboss_summary",
    "get_cached_summary",
]

