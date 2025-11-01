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
from typing import Optional, Dict, Any, Tuple
import requests
import streamlit as st

AMBOSS_URL: str = "https://content-mcp.de.production.amboss.com/mcp"


def _build_payload(query: str, *, language: str = "de") -> Dict[str, Any]:
    """Erstellt die JSON-RPC-Nutzlast für den MCP-Endpunkt von AMBOSS."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_article_sections",
            "arguments": {"query": query, "language": language},
        },
    }


def _try_parse_json(s: str) -> Optional[Any]:
    """Hilfsfunktion, um JSON robust zu parsen und Fehler still zu ignorieren."""
    try:
        return json.loads(s)
    except Exception:
        return None


def _looks_like_json(value: str) -> bool:
    """Prüft anhand einfacher Heuristiken, ob ein String JSON enthalten könnte."""
    stripped = value.strip()
    return (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    )


def _peel_json(obj_or_str: Any, *, max_depth: int = 4) -> Tuple[Any, int]:
    """Entpackt verschachtelte JSON-Strings schrittweise bis ``max_depth`` Ebenen.

    Rückgabewert ist ein ``(objekt, tiefe)``-Tupel. ``tiefe`` beschreibt, wie oft
    erfolgreich geparst wurde. Dies hilft dabei zu erkennen, ob tatsächlich eine
    weitere JSON-Struktur gefunden wurde.
    """

    depth = 0
    current = obj_or_str
    while depth < max_depth:
        if isinstance(current, str) and _looks_like_json(current):
            try:
                current = json.loads(current)
            except Exception:
                break
            depth += 1
            continue
        break
    return current, depth


def _parse_response(resp: requests.Response) -> dict:
    """Wertet die Antwort des MCP aus und verarbeitet klassische JSON- sowie SSE-Antworten."""
    ctype = resp.headers.get("Content-Type", "")
    if "application/json" in ctype and "event-stream" not in ctype:
        return resp.json()

    # ``resp.text`` blockiert solange, bis der Server die Antwort vollständig übertragen
    # hat. Damit beantworten wir die häufige Frage, ob der Stream eventuell „zu früh“
    # verarbeitet wird: Nein, Requests liefert hier erst weiter, sobald alle Daten
    # angekommen sind. Anschließend kann die SSE-Nutzlast in Ruhe ausgewertet werden.
    text_body = resp.text
    if "event-stream" in ctype or "data:" in text_body:
        # Jede ``data:``-Zeile wird separat betrachtet, damit selbst fragmentierte
        # SSE-Antworten korrekt ausgewertet werden. Wir merken uns das letzte
        # vollständige JSON-RPC-Objekt, das eine ``result``-Eigenschaft enthält.
        # Hinweise für Debugging: Bei Bedarf kann man temporär ``st.write(raw_line)``
        # aktivieren, um den Stream im Detail zu untersuchen.
        result_object: Optional[dict] = None
        for raw_line in text_body.splitlines():
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue

            data_payload = line[len("data:") :].strip()
            if not data_payload or data_payload == "[DONE]":
                continue

            # Erste Dekodierungsstufe: Direkt versuchen, den Payload zu laden.
            parsed_line = _try_parse_json(data_payload)
            current: Any = parsed_line if parsed_line is not None else data_payload

            # Weitere Dekodierungsstufen: Manche Antworten enthalten JSON in JSON.
            current, _ = _peel_json(current)

            if isinstance(current, dict):
                if "error" in current:
                    # Im Fehlerfall möchten wir die Informationen sofort anzeigen.
                    raise RuntimeError(f"MCP error: {current.get('error')}")
                if "result" in current:
                    result_object = current

        if result_object is None:
            # Für Debugging-Zwecke speichern wir den kompletten Rohtext, damit man
            # im Fehlerfall die Antwort manuell untersuchen kann.
            st.session_state["amboss_result_raw"] = {
                "hinweis": "Keine verwertbare JSON-RPC-Nutzlast in der SSE-Antwort gefunden.",
                "rohtext": text_body,
            }
            raise ValueError("Konnte keine JSON-RPC-Nutzlast aus SSE extrahieren.")

        # Falls die eigentliche Information nochmals als String vorliegt, versuchen
        # wir auch diese Ebene zu entpacken, damit nachgelagerte Module direkt mit
        # Python-Strukturen arbeiten können.
        try:
            content_entries = result_object.get("result", {}).get("content", [])
            for entry in content_entries:
                if entry.get("type") == "text" and isinstance(entry.get("text"), str):
                    unpacked, depth = _peel_json(entry["text"], max_depth=3)
                    if depth > 0 and isinstance(unpacked, (dict, list)):
                        entry["text"] = unpacked
            st.session_state["amboss_result_inner"] = result_object
        except Exception:
            # Sollte das Entpacken scheitern, verbleiben die Originalwerte; die
            # Funktion liefert dennoch die bisher ermittelten Daten zurück.
            pass

        st.session_state.pop("amboss_result_raw", None)
        return result_object

    # Alle anderen Content-Types werden explizit abgefangen, um unerwartete Antworten
    # früh zu erkennen. Auch hier landet der Rohtext im Session State für Debugging.
    st.session_state["amboss_result_raw"] = {
        "hinweis": "Unerwarteter Content-Type beim MCP-Aufruf.",
        "content_type": ctype,
        "rohtext": text_body,
    }
    raise ValueError(f"Unerwarteter Content-Type: {ctype}")


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
    # Der Aufruf blockiert bis zur vollständigen Antwort; erst danach geht es in der
    # Verarbeitung weiter. Wer experimentell live im Stream mitlesen möchte, kann
    # ``stream=True`` ergänzen und in ``_parse_response`` auf ``resp.iter_lines``
    # umstellen. Für die reguläre Nutzung ist das vollständige Puffern jedoch stabiler.
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
