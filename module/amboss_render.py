"""Hilfsfunktionen zur aufbereiteten Darstellung von AMBOSS-MCP-Antworten.

Die Funktionen in diesem Modul extrahieren Tabellen, strukturierte Inhalte und
roh eingebettete JSON-Fragmente aus den vom AMBOSS-MCP gelieferten Antworten.
Damit steht im Adminbereich sowie in Hilfstools dieselbe aufbereitete
Markdown-Darstellung zur Verfügung wie in ``mcp_streamable_test``.

Alle Kommentare sind bewusst ausführlich gehalten, um spätere Anpassungen und
Debugging zu erleichtern.
"""

from __future__ import annotations

import json
import re
from typing import Iterable, Optional


def fix_mojibake(text: str) -> str:
    """Repariert typische Kodierungsfehler, die in MCP-Antworten auftreten können."""

    if not isinstance(text, str):
        return text
    try:
        return text.encode("latin1").decode("utf-8")
    except Exception:
        # Sollte das Re-Encoding nicht funktionieren, werden einzelne bekannte
        # Platzhalter ersetzt. Für erweitertes Debugging kann hier eine
        # ``print``-Ausgabe aktiviert werden, um problematische Zeichenketten zu
        # identifizieren.
        replacements = (
            ("â€“", "–"),
            ("â€”", "—"),
            ("â€ž", "„"),
            ("â€œ", "“"),
            ("â€˜", "‚"),
            ("â€™", "’"),
            ("â€¡", "‡"),
            ("â€¢", "•"),
            ("Â", ""),
        )
        for old, new in replacements:
            text = text.replace(old, new)
        return text


def clean_placeholders(text: str, url: Optional[str] = None) -> str:
    """Bereinigt AMBOSS-spezifische Platzhalter und setzt †-Links sinnvoll um."""

    if not isinstance(text, str):
        return text
    cleaned = fix_mojibake(text)
    cleaned = cleaned.replace("{Sub}", "<sub>").replace("{/Sub}", "</sub>")
    cleaned = cleaned.replace("{Sup}", "<sup>").replace("{/Sup}", "</sup>")
    cleaned = cleaned.replace("{NewLine}", "<br>")
    if url:
        cleaned = re.sub(r"\{RefNote:[^}]+\}", f"[†]({url})", cleaned)
    else:
        cleaned = re.sub(r"\{RefNote:[^}]+\}", "†", cleaned)
    cleaned = re.sub(r"\{Ref[^\}]+\}", "", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned


def try_parse_json(text: str) -> Optional[dict]:
    """Versucht, einen JSON-String zu parsen; bei Fehlern wird ``None`` geliefert."""

    try:
        return json.loads(text)
    except Exception:
        # Für tiefergehendes Debugging kann hier ein Logging-Aufruf ergänzt
        # werden, der den fehlerhaften Ausschnitt mitsamt Exception protokolliert.
        return None


def try_parse_embedded_json_text(content_item_text: str) -> Optional[dict]:
    """Parst eingebettetes JSON, das innerhalb von Textsegmenten ausgeliefert wird."""

    if not isinstance(content_item_text, str):
        return None
    return try_parse_json(fix_mojibake(content_item_text))


def fix_inline_table_breaks(markdown: str) -> str:
    """Stellt sicher, dass Tabellen nicht durch ``<br>``-Zeilenumbrüche zerstört werden."""

    markdown = re.sub(r"(?:<br>\s*)+\|", r"\n|", markdown)
    markdown = re.sub(r"([^\n])\s*<br>\s*(\|)", r"\1\n\2", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown


def format_markdown_tables(markdown: str) -> str:
    """Normalisiert Tabellenblöcke und entfernt überflüssige Platzhalter."""

    lines = markdown.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)
    table_pattern = re.compile(r"^\s*\|.*\|\s*$")

    def clean_cell(cell: str) -> str:
        cell = cell.strip()
        cell = re.sub(r"^(?:<br>\s*)+", "", cell)
        cell = re.sub(r"(?:\s*<br>)+$", "", cell)
        cell = cell.replace("{NewLine}", "<br>")
        cell = re.sub(r"\{Ref[^}]*\}", "", cell)
        cell = re.sub(r"[ \t]{2,}", " ", cell).strip()
        return cell

    def is_separator(cell: str) -> bool:
        stripped = cell.strip()
        return len(stripped) >= 3 and set(stripped) <= set("-: ")

    while i < n:
        if table_pattern.match(lines[i]):
            block: list[str] = []
            while i < n and table_pattern.match(lines[i]):
                block.append(lines[i])
                i += 1

            rows = [row.strip().strip("|") for row in block]
            parsed_rows = [[clean_cell(cell) for cell in row.split("|")] for row in rows]

            max_cols = max((len(r) for r in parsed_rows), default=0)
            normalized_rows = [
                row + [""] * (max_cols - len(row))
                for row in parsed_rows
            ]

            if normalized_rows:
                if len(normalized_rows) == 1:
                    header = normalized_rows[0]
                    separator = ["---" if cell else "-" for cell in header]
                    normalized_rows.insert(1, separator)
                elif not any(is_separator(cell) for cell in normalized_rows[1]):
                    separator = [
                        cell if is_separator(cell) else "---"
                        for cell in normalized_rows[1]
                    ]
                    normalized_rows.insert(1, separator)

            formatted_rows = ["| " + " | ".join(row) + " |" for row in normalized_rows]
            out.extend(formatted_rows)
        else:
            out.append(lines[i])
            i += 1

    return "\n".join(out)


def extract_items_from_result(result: dict) -> list[dict]:
    """Liest Ergebnislisten aus ``structuredContent.results`` oder ``result.results`` aus."""

    if not isinstance(result, dict):
        return []
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        structured_results = structured.get("results")
        if isinstance(structured_results, list) and structured_results:
            return structured_results
    plain_results = result.get("results")
    if isinstance(plain_results, list) and plain_results:
        return plain_results
    return []


def render_items(items: Iterable[dict]) -> list[str]:
    """Erstellt Markdown-Blöcke für jedes Ergebnis inklusive Titel, Text und Links."""

    blocks: list[str] = []
    for item in items:
        title = (
            item.get("title")
            or item.get("article_title")
            or item.get("name")
            or "–"
        )
        snippet = item.get("snippet") or item.get("chunk") or ""
        url = item.get("url")
        eid = item.get("article_id") or item.get("eid") or item.get("id")

        pretty = clean_placeholders(snippet, url)
        try:
            pretty = fix_inline_table_breaks(pretty)
            pretty = format_markdown_tables(pretty)
        except Exception:
            # Falls die Bereinigung fehlschlägt, zeigen wir den Rohtext an. Für
            # eine detaillierte Analyse kann hier temporär ``raise`` gesetzt
            # werden, um den Fehler zu provozieren.
            pass

        block = f"**{fix_mojibake(title)}**\n\n{pretty}"
        if url:
            block += f"\n\n🔗 {url}"
        if eid:
            block += f"\n\n_EID/ID: {eid}_"
        blocks.append(block)
    return blocks


def build_pretty_markdown(data: dict) -> str:
    """Erstellt die aufbereitete Markdown-Ausgabe analog zur Testoberfläche."""

    if not isinstance(data, dict):
        return "Keine gültigen AMBOSS-Daten vorhanden."

    if "error" in data:
        error_obj = data["error"]
        message = error_obj.get("message", "Unbekannter Fehler")
        code = error_obj.get("code")
        return f"**Fehler:** {message}" + (f" (Code {code})" if code is not None else "")

    result = data.get("result", {})

    items = extract_items_from_result(result)
    if items:
        blocks = ["### Ergebnisse"]
        blocks.extend(render_items(items))
        markdown = ("\n\n---\n\n").join(blocks)
        return format_markdown_tables(fix_inline_table_breaks(markdown))

    if isinstance(result, dict) and "content" in result:
        content = result["content"]
        if isinstance(content, str):
            markdown = "### Inhalt (Text)\n\n" + clean_placeholders(content)
            markdown = fix_inline_table_breaks(markdown)
            return format_markdown_tables(markdown)
        if isinstance(content, list):
            embedded_blocks: list[str] = []
            parsed_any = False
            for segment in content:
                if (
                    isinstance(segment, dict)
                    and segment.get("type") == "text"
                    and isinstance(segment.get("text"), str)
                ):
                    embedded = try_parse_embedded_json_text(segment["text"])
                    if embedded:
                        parsed_any = True
                        embedded_items = (
                            embedded.get("results")
                            or embedded.get("data")
                            or []
                        )
                        if isinstance(embedded_items, list) and embedded_items:
                            embedded_blocks.extend(render_items(embedded_items))
                        else:
                            embedded_blocks.append(
                                "```json\n"
                                + json.dumps(embedded, ensure_ascii=False, indent=2)
                                + "\n```"
                            )
            if parsed_any and embedded_blocks:
                markdown = ("\n\n").join(
                    ["### Extrahierte Ergebnisse (eingebettetes JSON)"] + embedded_blocks
                )
                return format_markdown_tables(fix_inline_table_breaks(markdown))

            segment_blocks: list[str] = []
            for segment in content:
                if isinstance(segment, dict) and segment.get("type") == "text":
                    pretty = clean_placeholders(segment.get("text") or "")
                    pretty = fix_inline_table_breaks(pretty)
                    pretty = format_markdown_tables(pretty)
                    segment_blocks.append(pretty)
                else:
                    segment_blocks.append(
                        "```json\n"
                        + json.dumps(segment, ensure_ascii=False, indent=2)
                        + "\n```"
                    )
            markdown = ("\n\n---\n\n").join(["### Inhalt (Segmente)"] + segment_blocks)
            return format_markdown_tables(fix_inline_table_breaks(markdown))

        return (
            "Unbekanntes 'content'-Format:\n\n"
            "```json\n"
            + json.dumps(content, ensure_ascii=False, indent=2)
            + "\n```"
        )

    return (
        "Unbekannter 'result'-Inhalt:\n\n"
        "```json\n"
        + json.dumps(result, ensure_ascii=False, indent=2)
        + "\n```"
    )


def render_markdown_for_display(data: dict) -> str:
    """Bequeme Wrapper-Funktion, die das Ergebnis final für ``st.code`` aufbereitet."""

    markdown = build_pretty_markdown(data)
    markdown = fix_inline_table_breaks(markdown)
    markdown = format_markdown_tables(markdown)
    return markdown
