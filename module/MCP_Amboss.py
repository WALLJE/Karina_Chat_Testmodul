"""Vereinfachter AMBOSS-MCP-Client für Karina ohne eigene UI-Komponenten.

Zweck
-----
- Ruft ausschließlich das AMBOSS-MCP-Tool ``search_article_sections`` per JSON-RPC auf.
- Gibt das unveränderte JSON-Ergebnis zurück, damit andere Module flexibel darauf
  zugreifen können.
- Hinterlegt sowohl die Anfrage als auch das Ergebnis im ``st.session_state``.

Anwendung
---------
from module.MCP_Amboss import call_amboss_search

data = call_amboss_search(query="Ileitis terminalis")

Alle Kommentare in diesem Modul sind bewusst ausführlich gehalten, damit das Verhalten
auch für spätere Anpassungen nachvollziehbar bleibt. Für detailliertes Debugging können
zusätzliche ``st.write``-Ausgaben aktiviert werden, die aktuell aus Gründen der
Übersichtlichkeit auskommentiert bleiben.
"""

from __future__ import annotations
import json
from typing import Optional, Dict, Any
import requests
import streamlit as st

AMBOSS_URL: str = "https://content-mcp.de.production.amboss.com/mcp"


def _build_payload(query: str, *, language: str = "de") -> Dict[str, Any]:
    """Erstellt die JSON-RPC-Nutzlast für den MCP-Endpunkt von AMBOSS."""
    return {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {
            "name": "search_article_sections",
            "arguments": {"query": query, "language": language},
        },
    }


def _try_parse_json(s: str) -> Optional[dict]:
    """Hilfsfunktion, um JSON robust zu parsen und Fehler still zu ignorieren."""
    try:
        return json.loads(s)
    except Exception:
        return None


def _parse_response(resp: requests.Response) -> dict:
    """Wertet die Antwort des MCP aus und verarbeitet klassische JSON- sowie SSE-Antworten."""
    ctype = resp.headers.get("Content-Type", "")
    if "application/json" in ctype:
        return resp.json()

    # Verarbeitung von Server-Sent Events (SSE): AMBOSS liefert die JSON-Antwort
    # dabei zeilenweise und prefixiert jede Datenzeile mit "data:". Die folgende
    # Schleife entfernt diesen Prefix und setzt die JSON-Segmente wieder korrekt
    # zusammen. Sollte der Dienst in Zukunft ein anderes Format liefern, kann hier
    # das Debugging über auskommentierte ``st.write``-Anweisungen erfolgen.
    payload = "".join(
        line.strip()[len("data:"):].strip()
        for line in resp.text.splitlines()
        if line.strip().startswith("data:")
    )
    parsed = _try_parse_json(payload)
    if parsed is None:
        # Um Fehlerszenarien im Adminbereich besser nachvollziehen zu können,
        # sichern wir den gesamten SSE-Rohtext sowie den zusammengesetzten Payload
        # im Session State. So lassen sich die Daten später komfortabel inspizieren
        # und bei Bedarf kopieren, ohne das Standardverhalten zu verändern.
        st.session_state["amboss_result_raw"] = {
            "hinweis": "JSON-Parsing der SSE-Nutzlast fehlgeschlagen.",
            "rohtext": resp.text,
            "zusammengefuehrter_payload": payload,
        }
        raise ValueError("Konnte SSE-JSON nicht extrahieren.")
    # Erfolgreiche Antworten räumen den Rohdaten-Eintrag auf, damit keine veralteten
    # Inhalte in der Adminansicht verbleiben.
    st.session_state.pop("amboss_result_raw", None)
    return parsed


def call_amboss_search(
    *,
    query: str,
    token: Optional[str] = None,
    url: str = AMBOSS_URL,
    timeout: float = 30.0,
    language: str = "de",
    extra_headers: Optional[Dict[str, str]] = None,
) -> dict:
    """Ruft ``search_article_sections`` auf und legt das Roh-JSON im Session State ab.

    Falls kein Token übergeben wird, wird automatisch ``st.secrets["Amboss_Token"]``
    verwendet. Sowohl die Nutzlast als auch das Ergebnis werden im ``st.session_state``
    gespeichert, damit andere Module direkt darauf zugreifen können.
    """
    token = token or st.secrets.get("Amboss_Token")
    if not token:
        raise ValueError("Amboss_Token not found. Please set in st.secrets or pass as argument.")

    payload = _build_payload(query, language=language)
    st.session_state["amboss_input_mcp"] = payload

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if extra_headers:
        headers.update(extra_headers)

    # Debug-Hinweis: Bei Bedarf kann hier ``st.write(headers, payload)`` aktiviert werden,
    # um die Anfrage im Detail zu inspizieren.
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
    resp.raise_for_status()
    result = _parse_response(resp)

    st.session_state["amboss_result"] = result
    return result


if __name__ == "__main__":
    import os, argparse, json

    parser = argparse.ArgumentParser(description="Call AMBOSS MCP search_article_sections.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument("--token", default=os.environ.get("Amboss_Token"), help="AMBOSS Bearer token")
    parser.add_argument("--language", default="de", help="Language parameter for MCP")
    args = parser.parse_args()

    result = call_amboss_search(query=args.query, token=args.token, language=args.language)
    print(json.dumps(result, ensure_ascii=False, indent=2))
