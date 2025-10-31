"""Erstellt das Abschlussfeedback in mehreren parallelen Abschnitten."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from module.token_counter import init_token_counters
from module.patient_language import get_patient_forms
from module.offline import get_offline_feedback, is_offline
from module.feedback_mode import (
    FEEDBACK_MODE_AMBOSS_CHATGPT,
    determine_feedback_mode,
)
from module.amboss_preprocessing import ensure_amboss_summary
from module.feedback_parallel import (
    assemble_feedback_output,
    build_feedback_aspects,
    build_feedback_base_context,
    run_parallel_feedback_requests,
)


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
    diagnose_szenario,
):
    """Generiert das strukturierte Abschlussfeedback mit parallelen API-Aufrufen."""

    feedback_mode = determine_feedback_mode()

    if is_offline():
        return get_offline_feedback(diagnose_szenario)

    patient_forms = get_patient_forms()

    # Tokenzähler initialisieren, damit sowohl die AMBOSS-Vorverarbeitung als
    # auch die nachfolgenden Feedback-Aufrufe sauber protokolliert werden.
    init_token_counters()

    amboss_summary: Optional[str] = None
    if feedback_mode == FEEDBACK_MODE_AMBOSS_CHATGPT:
        patient_age = int(st.session_state.get("patient_age", 0) or 0)
        amboss_summary = ensure_amboss_summary(
            client,
            diagnose_szenario=diagnose_szenario,
            patient_age=patient_age,
        )

    base_context = build_feedback_base_context(
        patient_phrase=patient_forms.phrase("dat", article="definite"),
        diagnose_szenario=diagnose_szenario,
        final_diagnose=final_diagnose,
        therapie_vorschlag=therapie_vorschlag,
        user_ddx2=user_ddx2,
        diagnostik_eingaben=diagnostik_eingaben,
        gpt_befunde=gpt_befunde,
        koerper_befund=koerper_befund,
        user_verlauf=user_verlauf,
        anzahl_termine=anzahl_termine,
        amboss_summary=amboss_summary,
    )

    aspects = build_feedback_aspects(
        diagnose_szenario=diagnose_szenario,
        user_ddx2=user_ddx2,
        anzahl_termine=anzahl_termine,
    )

    aspect_results = run_parallel_feedback_requests(
        client,
        aspects=aspects,
        base_context=base_context,
        model="gpt-4",
        temperature=0.4,
    )

    return assemble_feedback_output(aspect_results)

