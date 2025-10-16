"""Helper utilities for admin data exports."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Dict, Iterable, Tuple

import pandas as pd
import streamlit as st
from cryptography.fernet import Fernet, InvalidToken
from supabase import Client, create_client


class FeedbackExportError(Exception):
    """Custom error raised for feedback export issues."""


def _get_supabase_client() -> Client:
    """Create and return a Supabase client using Streamlit secrets.

    Raises:
        FeedbackExportError: If Supabase credentials are missing or invalid.

    Returns:
        Client: An authenticated Supabase client instance.
    """

    supabase_config = st.secrets.get("supabase")
    if not supabase_config:
        raise FeedbackExportError("Supabase-Konfiguration fehlt in st.secrets.")

    try:
        url = supabase_config["url"]
        key = supabase_config["key"]
    except KeyError as exc:
        raise FeedbackExportError("Supabase-Zugangsdaten sind unvollständig.") from exc

    try:
        client = create_client(url, key)
    except Exception as exc:  # pragma: no cover - defensive
        raise FeedbackExportError(f"Supabase-Verbindung fehlgeschlagen: {exc!r}") from exc

    return client


def _get_matrikel_fernet() -> Fernet:
    """Create the Fernet instance for matrikel token decryption."""

    supabase_config = st.secrets.get("supabase")
    if not supabase_config or "matrikel_key" not in supabase_config:
        raise FeedbackExportError("Supabase-Geheimnis 'matrikel_key' fehlt.")

    matrikel_key = supabase_config["matrikel_key"]
    if not matrikel_key:
        raise FeedbackExportError("Supabase 'matrikel_key' ist leer.")

    try:
        return Fernet(matrikel_key)
    except Exception as exc:  # pragma: no cover - defensive
        raise FeedbackExportError("Supabase 'matrikel_key' ist ungültig.") from exc


def _decrypt_matrikel_values(
    rows: Iterable[Dict[str, object]],
    fernet: Fernet,
) -> None:
    """Mutate rows in-place by decrypting 'Matrikel' tokens if present."""

    for row in rows:
        token = row.get("Matrikel")
        if not token:
            row["Matrikel"] = "(nicht angegeben)"
            continue

        if not isinstance(token, str):
            row["Matrikel"] = "(ungültiges Format)"
            continue

        try:
            decrypted = fernet.decrypt(token.encode("utf-8")).decode("utf-8")
            row["Matrikel"] = decrypted
        except InvalidToken:
            row["Matrikel"] = "(Entschlüsselung fehlgeschlagen)"
        except Exception:  # pragma: no cover - defensive
            row["Matrikel"] = "(Entschlüsselung fehlgeschlagen)"


def build_feedback_export() -> Tuple[bytes, str]:
    """Fetch GPT feedback entries and return an Excel export as bytes.

    Raises:
        FeedbackExportError: If accessing Supabase or the secrets fails.

    Returns:
        Tuple[bytes, str]: The Excel file bytes and a suggested filename.
    """

    client = _get_supabase_client()
    fernet = _get_matrikel_fernet()

    try:
        response = client.table("feedback_gpt").select("*").execute()
    except Exception as exc:  # pragma: no cover - defensive
        raise FeedbackExportError(f"Abruf aus Supabase fehlgeschlagen: {exc!r}") from exc

    if getattr(response, "error", None):
        raise FeedbackExportError(f"Supabase meldet einen Fehler: {response.error}")

    rows: Iterable[Dict[str, object]] = response.data or []
    rows = [dict(row) for row in rows]

    _decrypt_matrikel_values(rows, fernet)

    df = pd.DataFrame(rows)

    if df.empty:
        df = pd.DataFrame(columns=["ID", "Matrikel", "datum", "uhrzeit"])

    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)

    filename = f"feedback_gpt_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    return buffer.getvalue(), filename
