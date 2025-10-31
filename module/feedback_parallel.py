"""Werkzeuge für die parallele Erstellung der Feedback-Abschnitte.

Die vorherige Implementierung erzeugte einen einzigen Prompt, der alle
Bewertungsdimensionen nacheinander abfragte. Dadurch wartete der Client auf eine
lange Antwort. Dieses Modul kapselt nun die Aufteilung in thematische
Einzelabschnitte, die zeitgleich an die ChatGPT-API geschickt werden können.
Alle Kommentare sind bewusst ausführlich und auf Deutsch gehalten, damit die
Arbeitsweise leicht nachvollziehbar bleibt.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from module.token_counter import add_usage

# System-Prompt, der für sämtliche Teilanfragen genutzt wird. Dadurch erhalten
# alle Abschnitte dieselben Grundregeln, ohne dass sie in jedem Prompt erneut
# formuliert werden müssen.
_SYSTEM_PROMPT = (
    "Du bist ein erfahrener medizinischer Prüfer. Du sprichst die studierende "
    "Person konsequent mit 'du' an, schreibst auf Deutsch und begründest deine "
    "Wertungen fachlich. Bewerte ausschließlich die Nutzer-Eingaben und keine "
    "automatisch generierten Assistentenantworten."
)


@dataclass(frozen=True)
class FeedbackAspect:
    """Repräsentiert einen Teilbereich des Abschlussfeedbacks."""

    identifier: str
    title: str
    instruction: str
    enumerated: bool = True


def build_feedback_base_context(
    *,
    patient_phrase: str,
    diagnose_szenario: str,
    final_diagnose: str,
    therapie_vorschlag: str,
    user_ddx2: str,
    diagnostik_eingaben: str,
    gpt_befunde: str,
    koerper_befund: str,
    user_verlauf: str,
    anzahl_termine: int,
    amboss_summary: str | None = None,
) -> str:
    """Bereitet den gemeinsamen Textkontext für alle Teilprompts auf."""

    # Alle Eingaben werden in menschenlesbare Strings umgewandelt, damit auch
    # leere Felder sauber ausgewiesen werden. Für detailliertes Debugging kann
    # an den kommentierten Stellen eine ``print``-Anweisung ergänzt werden.
    def _fmt(value) -> str:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else "–"
        if value:
            return str(value)
        return "–"

    conversation = str(user_verlauf or "")

    basis = [
        "Kontext für die Bewertung:",
        f"- Szenariodiagnose: { _fmt(diagnose_szenario)}",
        f"- Anzahl der diagnostischen Termine: {anzahl_termine}",
        f"- Finale Diagnose laut Studierendem: { _fmt(final_diagnose)}",
        f"- Therapievorschlag laut Studierendem: { _fmt(therapie_vorschlag)}",
        f"- Differentialdiagnosen laut Studierendem: { _fmt(user_ddx2)}",
        f"- Geplante Diagnostik laut Studierendem: { _fmt(diagnostik_eingaben)}",
        f"- GPT-generierte Befunde (nur Kontext, nicht bewerten): { _fmt(gpt_befunde)}",
        f"- Körperliche Untersuchung (nur Kontext, nicht bewerten): { _fmt(koerper_befund)}",
        "",
        "Gesprächsprotokoll (bewerte nur die Nutzereingaben, nicht die Antworten ",
        f"{patient_phrase}):",
        conversation.strip() or "–",
    ]

    if amboss_summary:
        basis.extend(
            [
                "",
                "Verdichtete AMBOSS-Fachinformationen (bereits vorverarbeitet):",
                amboss_summary.strip(),
            ]
        )

    basis.extend(
        [
            "",
            "Allgemeine Hinweise:",
            "- Vermeide Aufzählungen mit Spiegelstrichen und formuliere flüssige Absätze.",
            "- Benenne explizit Stärken und Verbesserungsbedarf.",
            "- Beziehe dich immer auf die Entscheidungsqualität der studierenden Person.",
        ]
    )

    return "\n".join(basis)


def build_feedback_aspects(
    diagnose_szenario: str,
    user_ddx2: str,
    anzahl_termine: int,
) -> List[FeedbackAspect]:
    """Erzeugt die Liste der Bewertungsabschnitte in der gewünschten Reihenfolge."""

    return [
        FeedbackAspect(
            identifier="overview",
            title="Überblick zum Szenario",
            instruction=(
                "Gib eine kurze Einleitung. Nenne das Szenario explizit, bewerte "
                "ob die finale Diagnose zum Szenario passt und erwähne die Anzahl der "
                f"Diagnostik-Termine ({anzahl_termine}). Zeige auf, ob der Gesamteindruck "
                "stimmig ist."
            ),
            enumerated=False,
        ),
        FeedbackAspect(
            identifier="anamnese",
            title="Anamnese",
            instruction=(
                "Analysiere, ob die anamnestischen Informationen vollständig und zielgerichtet erhoben wurden. "
                "Gehe sowohl auf gelungene Fragen als auch auf ausgelassene Aspekte ein."
            ),
        ),
        FeedbackAspect(
            identifier="diagnostik_szenario",
            title="Diagnostik bezogen auf die Hauptdiagnose",
            instruction=(
                "Bewerte, ob die geplanten Untersuchungen geeignet sind, die Szenariodiagnose "
                f"{diagnose_szenario} zu sichern. Beschreibe fehlende oder überflüssige Schritte."
            ),
        ),
        FeedbackAspect(
            identifier="differentialdiagnosen",
            title="Differentialdiagnosen",
            instruction=(
                "Diskutiere die genannten Differentialdiagnosen ({user_ddx2}). Erkläre, "
                "wie gut sie abgegrenzt wurden und welche Diagnostik dazu nötig wäre."
            ),
        ),
        FeedbackAspect(
            identifier="strategie",
            title="Diagnostische Strategie",
            instruction=(
                "Beurteile die Reihenfolge der Maßnahmen und die Planung der Termine. "
                "Zeige auf, wo Struktur oder Priorisierung verbessert werden kann."
            ),
        ),
        FeedbackAspect(
            identifier="finale_diagnose",
            title="Finale Diagnose",
            instruction=(
                "Stelle heraus, ob die finale Diagnose fachlich abgesichert ist. "
                "Vergleiche mit alternativen Erklärungen und nenne fehlende Begründungen."
            ),
        ),
        FeedbackAspect(
            identifier="therapie",
            title="Therapie",
            instruction=(
                "Bewerte die Therapieplanung hinsichtlich Leitlinien, Individualisierung "
                "und Sicherheitsaspekten. Empfiehl konkrete Verbesserungen."
            ),
        ),
        FeedbackAspect(
            identifier="nachhaltigkeit",
            title="Ökologie und Ökonomie",
            instruction=(
                "Analysiere ökologische und ökonomische Folgen der Entscheidungen. "
                "Beschreibe Ressourcenverbrauch, Strahlenbelastung sowie unnötige oder fehlende Maßnahmen."
            ),
            enumerated=False,
        ),
    ]


async def _request_single_aspect(
    client,
    *,
    model: str,
    temperature: float,
    base_context: str,
    aspect: FeedbackAspect,
) -> str:
    """Sendet eine einzelne Teilanfrage an die ChatGPT-API."""

    prompt = (
        f"{base_context}\n\nAufgabe für den Abschnitt '{aspect.title}':\n"
        f"{aspect.instruction}\n\nFormuliere einen kompakten Absatz."
    )

    def _call_api() -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        add_usage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        )
        return response.choices[0].message.content.strip()

    return await asyncio.to_thread(_call_api)


def run_parallel_feedback_requests(
    client,
    *,
    aspects: Sequence[FeedbackAspect],
    base_context: str,
    model: str,
    temperature: float,
) -> List[Tuple[FeedbackAspect, str]]:
    """Führt alle Teilanfragen parallel aus und gibt sie in ursprünglicher Reihenfolge zurück."""

    async def _run() -> List[str]:
        tasks = [
            asyncio.create_task(
                _request_single_aspect(
                    client,
                    model=model,
                    temperature=temperature,
                    base_context=base_context,
                    aspect=aspect,
                )
            )
            for aspect in aspects
        ]
        return await asyncio.gather(*tasks)

    results = asyncio.run(_run())
    return list(zip(aspects, results))


def assemble_feedback_output(aspect_results: Iterable[Tuple[FeedbackAspect, str]]) -> str:
    """Setzt die einzelnen Abschnittstexte zu einem strukturierten Feedback zusammen."""

    lines: List[str] = []
    counter = 1
    for aspect, text in aspect_results:
        if aspect.enumerated:
            heading = f"{counter}. {aspect.title}"
            counter += 1
        else:
            heading = aspect.title
        lines.append(f"**{heading}**\n{text.strip()}")

    return "\n\n".join(lines)


__all__ = [
    "FeedbackAspect",
    "assemble_feedback_output",
    "build_feedback_aspects",
    "build_feedback_base_context",
    "run_parallel_feedback_requests",
]

