"""Erstellung des Abschlussfeedbacks mit wählbarem Modus.

Die Funktion ``feedback_erzeugen`` liefert weiterhin das strukturierte
Abschlussfeedback, berücksichtigt nun aber je nach Modus zusätzlich die
AMBOSS-Ergebnisse. Die Kommentare sind bewusst ausführlich gehalten, damit
Anpassungen (z. B. neue Feedback-Modi) schnell nachvollzogen werden können.
"""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from module.token_counter import init_token_counters, add_usage
from module.patient_language import get_patient_forms
from module.offline import get_offline_feedback, is_offline
from module.feedback_mode import (
    FEEDBACK_MODE_AMBOSS_CHATGPT,
    determine_feedback_mode,
)


def _format_amboss_result(data: Any) -> str:
    """Bereitet die AMBOSS-Antwort für den Prompt in Textform auf."""

    if not data:
        return "Keine AMBOSS-Daten im Session State gefunden."

    try:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    except TypeError:
        text = str(data)

    max_length = 4000
    if len(text) > max_length:
        # Debug-Hinweis: Für eine ausführliche Analyse kann dieser Abschnitt
        # temporär deaktiviert oder der Grenzwert erhöht werden.
        text = text[:max_length] + "\n\n[Ausgabe wegen Länge gekürzt]"
    return text


def feedback_erzeugen(
    client,
    final_diagnose,
    therapie_vorschlag,
    user_ddx2,
    diagnostik_eingaben,
    gpt_befunde,
    koerper_befund,
    user_verlauf,
    anzahl_termine,
    diagnose_szenario
):
    """Generiert das Feedback unter Beachtung des gewählten Feedback-Modus."""

    feedback_mode = determine_feedback_mode()

    if is_offline():
        return get_offline_feedback(diagnose_szenario)

    patient_forms = get_patient_forms()

    prompt = f"""
Ein Medizinstudierender hat eine vollständige virtuelle Fallbesprechung mit {patient_forms.phrase("dat", article="indefinite")}
durchgeführt. Du bist ein erfahrener medizinischer Prüfer.

Beurteile ausschließlich die Eingaben und Entscheidungen des Studierenden – NICHT die Antworten {patient_forms.phrase("gen")} oder automatisch generierte Inhalte.

Die zugrunde liegende Erkrankung im Szenario lautet: **{diagnose_szenario}**.

Hier ist der Gesprächsverlauf mit den Fragen und Aussagen des Nutzers:
{user_verlauf}

GPT-generierte Befunde (nur als Hintergrund, bitte nicht bewerten):
{koerper_befund}
{gpt_befunde}

Erhobene Differentialdiagnosen (Nutzerangaben):
{user_ddx2}

Geplante diagnostische Maßnahmen (Nutzerangaben):
{diagnostik_eingaben}

Finale Diagnose (Nutzereingabe):
{final_diagnose}

Therapiekonzept (Nutzereingabe):
{therapie_vorschlag}

Die Fallbearbeitung umfasste {anzahl_termine} Diagnostik-Termine.

Strukturiere dein Feedback klar, hilfreich und differenziert – wie ein persönlicher Kommentar bei einer mündlichen Prüfung, schreibe in der zweiten Person.

Nenne vorab das zugrunde liegende Szenario. Gib an, ob die Diagnose richtig gestellt wurde. Gib an, wieviele Termine für die Diagnostik benötigt wurden.

1. Wurden im Gespräch alle relevanten anamnestischen Informationen erhoben?
2. War die gewählte Diagnostik nachvollziehbar, vollständig und passend zur Szenariodiagnose **{diagnose_szenario}**?
3. War die gewählte Diagnostik nachvollziehbar, vollständig und passend zu den Differentialdiagnosen **{user_ddx2}**?
4. Beurteile, ob die diagnostische Strategie sinnvoll aufgebaut war, beachte dabei die Zahl der notwendigen Untersuchungstermine. Gab es unnötige Doppeluntersuchungen, sinnvolle Eskalation, fehlende Folgeuntersuchungen? Beziehe dich ausdrücklich auf die Reihenfolge und den Inhalt der Runden.
5. Ist die finale Diagnose nachvollziehbar, insbesondere im Hinblick auf Differenzierung zu anderen Möglichkeiten?
6. Ist das Therapiekonzept leitliniengerecht, plausibel und auf die Diagnose abgestimmt?

**Berücksichtige und kommentiere zusätzlich**:
- ökologische Aspekte (z. B. überflüssige Diagnostik, zuviele Anforderungen, zuviele Termine, CO₂-Bilanz, Strahlenbelastung bei CT oder Röntgen, Ressourcenverbrauch).
- ökonomische Sinnhaftigkeit (Kosten-Nutzen-Verhältnis)
- Beachte und begründe auch, warum zuwenig Diagnostik unwirtschaftlich und nicht nachhaltig sein kann.
"""

    if feedback_mode == FEEDBACK_MODE_AMBOSS_CHATGPT:
        amboss_context = _format_amboss_result(st.session_state.get("amboss_result"))
        prompt += f"""

Zusätzliche Fachinformationen (AMBOSS):
{amboss_context}
"""

    init_token_counters()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    # prompt token: Einagbe an GPT
    # completion toke: Ausgabe von GPT
    add_usage(
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens
    )
    return response.choices[0].message.content
