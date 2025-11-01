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
import time

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


def _recover_partial_json(fragment: str) -> Optional[Any]:
    """Versucht, aus einem abgeschnittenen JSON-Fragment einen verwertbaren Teil zu extrahieren."""

    # Wir prüfen ausschließlich Fragmente, die mit ``}`` oder ``]`` enden. Nur dann
    # besteht eine realistische Chance, dass zumindest ein Teilobjekt vollständig
    # vorliegt. Der längste, gültige Präfix wird beibehalten, kürzere Varianten
    # dienen als Fallback für stark fragmentierte Antworten.
    stripped = fragment.strip()
    if not stripped:
        return None

    candidate_indices = [
        index for index, char in enumerate(stripped) if char in {"}", "]"}
    ]
    for index in reversed(candidate_indices):
        candidate = stripped[: index + 1]
        parsed = _try_parse_json(candidate)
        if parsed is not None:
            return parsed

    return None


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
    """Wertet die Antwort des MCP aus und verarbeitet klassische JSON- sowie SSE-Antworten.

    Hinweis zur Synchronität: ``requests`` liest den Body bei ``resp.text`` blockierend
    ein. Erst wenn der Server die komplette Antwort übertragen hat, wird diese Funktion
    aktiv. Eine vermeintlich „halbierte“ Nutzlast entsteht daher nicht durch zu frühes
    Parsen, sondern allenfalls durch einen Abbruch auf Serverseite. Für solche Fälle
    empfehlen sich die unten erwähnten Debug-Helfer, um den Rohtext zu untersuchen.
    """
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "application/json" in ctype and "event-stream" not in ctype:
        return resp.json()

    # ``resp.text`` blockiert solange, bis der Server die Antwort vollständig übertragen
    # hat. Damit beantworten wir die häufige Frage, ob der Stream eventuell „zu früh“
    # verarbeitet wird: Nein, Requests liefert hier erst weiter, sobald alle Daten
    # angekommen sind. Anschließend kann die SSE-Nutzlast in Ruhe ausgewertet werden.
    # Dank des blockierenden Leseverhaltens erhalten wir hier stets den vollständigen
    # Stream. Sollte der Server die Übertragung unerwartet abbrechen, wäre ``resp.text``
    # bereits verkürzt. In so einem Fall lässt sich die Ursache über die Debug-Hilfen
    # („amboss_result_raw“) nachvollziehen.
    text_body = resp.text
    if "event-stream" in ctype or "data:" in text_body or "event:" in text_body:
        # Viele SSE-Server stückeln ein einzelnes Event auf mehrere ``data:``-Zeilen
        # und trennen Events durch Leerzeilen. Deshalb puffern wir jede Sequenz von
        # ``data:``-Zeilen, fügen sie vor dem Parsen zusammen und ignorieren
        # Kommentar-/Keep-Alive-Zeilen. Für Debugging kann hier temporär ein
        # ``st.write(raw_line)`` ergänzt werden, um den Stream vollständig sichtbar
        # zu machen.
        events: list[str] = []
        buffer: list[str] = []
        for raw_line in text_body.splitlines():
            line = raw_line.rstrip("\r\n")
            if line == "":
                if buffer:
                    events.append("\n".join(buffer))
                    buffer = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                buffer.append(line[len("data:") :].lstrip())
                continue
            # Andere SSE-Felder wie ``event:`` benötigen wir hier nicht explizit, sie
            # werden für die JSON-Extraktion ignoriert.
        if buffer:
            events.append("\n".join(buffer))

        result_object: Optional[dict] = None
        for payload in events:
            if not payload or payload == "[DONE]":
                continue

            # Erste Dekodierungsstufe: Direkt versuchen, den Payload zu laden.
            current: Any = _try_parse_json(payload)
            if current is None:
                current = payload

            # Weitere Dekodierungsstufen: Manche Antworten enthalten JSON in JSON.
            current, _ = _peel_json(current)

            if isinstance(current, dict):
                if "error" in current:
                    raise RuntimeError(f"MCP error: {current.get('error')}")
                if "result" in current:
                    result_object = current

        if result_object is None:
            # Sicherung: Wir bewahren das erste verwertbare Fragment auf, damit die
            # Anwendung trotz abgebrochener Serverantwort weiterarbeiten kann. Das
            # Ergebnis wird klar als unvollständig markiert, sodass nachgelagerte
            # Schritte reagieren können.
            fallback_payload: Optional[str] = next(
                (payload for payload in events if payload and payload != "[DONE]"),
                None,
            )
            partial_object = (
                _recover_partial_json(fallback_payload) if fallback_payload else None
            )

            fallback_result: Dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": None,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                partial_object
                                if partial_object is not None
                                else fallback_payload
                                if fallback_payload is not None
                                else ""
                            ),
                        }
                    ]
                },
                "meta": {
                    "hinweis": "Fragment aus abgebrochener SSE-Antwort rekonstruiert.",
                    "unvollstaendig": True,
                },
            }

            st.session_state["amboss_result_raw"] = {
                "hinweis": "Keine vollständige JSON-RPC-Nutzlast in der SSE-Antwort gefunden.",
                "rohtext": text_body,
                "fragment": fallback_payload,
                "fragment_teilobjekt": partial_object,
            }
            st.session_state["amboss_result_unvollstaendig"] = True
            st.session_state["amboss_result_sicherung"] = {
                "hinweis": "Teilantwort aufgrund eines Verbindungsabbruchs gespeichert.",
                "fragment_quelle": "sse_event",
                "fragment_text": fallback_payload,
                "fragment_teilobjekt": partial_object,
            }
            return fallback_result

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
            # Sollte das Entpacken wider Erwarten scheitern, kann durch temporäre
            # ``st.write(entry)``-Ausgaben oberhalb geprüft werden, welche Struktur
            # genau vorliegt. Wir lassen in diesem Fall den Originaltext unangetastet.
            pass

        st.session_state.pop("amboss_result_unvollstaendig", None)
        st.session_state.pop("amboss_result_sicherung", None)
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
    max_retries: int = 0,
    retry_delay_seconds: float = 0.0,
) -> dict:
    """Ruft ``search_article_sections`` auf und legt das Roh-JSON im Session State ab.

    Falls kein Token übergeben wird, wird automatisch ``st.secrets["Amboss_Token"]``
    verwendet. Sowohl die Nutzlast als auch das Ergebnis werden im ``st.session_state``
    gespeichert, damit andere Module direkt darauf zugreifen können.

    Parameter ``max_retries`` erlaubt optional erneute Versuche, falls Netzwerkfehler
    oder unerwartete Antwortformate auftreten. Mit ``retry_delay_seconds`` kann eine
    Wartezeit zwischen den Versuchen hinterlegt werden, um den Server nicht sofort
    erneut zu belasten. Bei ``max_retries=0`` bleibt das bisherige Verhalten unverändert.
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
    attempts_total = max(0, int(max_retries)) + 1
    delay_seconds = max(0.0, float(retry_delay_seconds))

    # Dieses Dictionary speichert Details zum letzten Fehler. So lässt sich in der
    # App nachvollziehen, warum ggf. mehrere Versuche notwendig waren. Nach einem
    # erfolgreichen Durchlauf wird der Eintrag entfernt.
    last_error_info: Optional[Dict[str, Any]] = None

    for attempt_index in range(1, attempts_total + 1):
        try:
            resp = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=timeout,
            )
            resp.raise_for_status()
            result = _parse_response(resp)
        except (requests.RequestException, ValueError) as exc:
            # Fehlerfall: Wir notieren Versuchszähler und Fehlertyp für spätere Analyse.
            last_error_info = {
                "versuch": attempt_index,
                "max_versuche": attempts_total,
                "fehlertyp": type(exc).__name__,
                "fehlermeldung": str(exc),
            }
            st.session_state["amboss_letzter_fehlversuch"] = last_error_info

            if attempt_index < attempts_total:
                # Bei Bedarf kann hier temporär ``st.write(last_error_info)``
                # aktiviert werden, um die genauen Fehlermeldungen direkt in der
                # Oberfläche einzusehen.
                if delay_seconds > 0.0:
                    time.sleep(delay_seconds)
                continue

            # Sind alle Versuche ausgeschöpft, wird der ursprüngliche Fehler erneut
            # ausgelöst. Die letzte Fehlermeldung bleibt im Session State erhalten und
            # unterstützt beim Debugging.
            raise
        else:
            # Erfolgreicher Durchlauf: Wir räumen eventuelle Fehlereinträge wieder auf,
            # damit andere Module ausschließlich gültige Ergebnisse vorfinden.
            st.session_state.pop("amboss_letzter_fehlversuch", None)
            st.session_state["amboss_result"] = result
            return result

    # Defensive Rückgabe, sollte der Kontrollfluss unerwartet hier landen. Durch die
    # Schleifenlogik dürfte dieser Punkt zwar nie erreicht werden, das Statement macht
    # für statische Codeprüfungen deutlich, dass kein ``None`` zurückgegeben wird.
    raise RuntimeError("Unerwarteter Kontrollfluss in call_amboss_search")


if __name__ == "__main__":
    import os, argparse, json

    parser = argparse.ArgumentParser(description="Call AMBOSS MCP search_article_sections.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument("--token", default=os.environ.get("Amboss_Token"), help="AMBOSS Bearer token")
    parser.add_argument("--language", default="de", help="Language parameter for MCP")
    args = parser.parse_args()

    result = call_amboss_search(query=args.query, token=args.token, language=args.language)
    print(json.dumps(result, ensure_ascii=False, indent=2))
