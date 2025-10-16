"""Hilfsfunktionen für genderadaptive Patientenformulierungen."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import streamlit as st

_CASE_ALIASES = {
    "nom": "nom",
    "nominative": "nom",
    "acc": "acc",
    "accusative": "acc",
    "dat": "dat",
    "dative": "dat",
    "gen": "gen",
    "genitive": "gen",
}


@dataclass(frozen=True)
class PatientForms:
    """Enthält sprachliche Formen für die Patient:innenansprache."""

    definite: Dict[str, str]
    indefinite: Dict[str, str]
    plural: str
    compound_stem: str
    base: str
    relative_pronouns: Dict[str, str]

    def phrase(
        self,
        case: str = "nominative",
        *,
        article: str = "definite",
        adjective: str | None = None,
        capitalize: bool = False,
    ) -> str:
        """Gibt die gewünschte Form zurück."""

        case_key = _CASE_ALIASES.get(case.lower())
        if case_key is None:
            raise ValueError(f"Unsupported grammatical case: {case}")

        if article == "definite":
            phrase = self.definite[case_key]
        elif article == "indefinite":
            phrase = self.indefinite[case_key]
        else:
            raise ValueError(f"Unsupported article type: {article}")

        if adjective:
            parts = phrase.split(" ", 1)
            if len(parts) == 2:
                phrase = f"{parts[0]} {adjective} {parts[1]}"
            else:
                phrase = f"{adjective} {phrase}"

        if capitalize and phrase:
            phrase = phrase[0].upper() + phrase[1:]

        return phrase

    def plural_phrase(self, adjective: str | None = None) -> str:
        """Pluralbezeichnung mit optionalem Adjektiv."""

        if adjective:
            return f"{adjective} {self.plural}"
        return self.plural

    def compound(self, suffix: str) -> str:
        """Bildet zusammengesetzte Substantive."""

        return f"{self.compound_stem}{suffix}"

    def base_word(self) -> str:
        """Gibt das Grundwort (Singular) zurück."""

        return self.base

    def relative_pronoun(self, case: str = "nominative") -> str:
        """Gibt das passende Relativpronomen für den gewünschten Kasus zurück."""

        case_key = _CASE_ALIASES.get(case.lower())
        if case_key is None:
            raise ValueError(f"Unsupported grammatical case: {case}")

        return self.relative_pronouns[case_key]


def get_patient_forms() -> PatientForms:
    """Ermittelt passende sprachliche Formen anhand des gespeicherten Geschlechts."""

    gender = str(st.session_state.get("patient_gender", "")).strip().lower()

    if gender == "m":
        definite = {
            "nom": "der Patient",
            "acc": "den Patienten",
            "dat": "dem Patienten",
            "gen": "des Patienten",
        }
        indefinite = {
            "nom": "ein Patient",
            "acc": "einen Patienten",
            "dat": "einem Patienten",
            "gen": "eines Patienten",
        }
        plural = "Patienten"
        compound_stem = "Patienten"
        base = "Patient"
        relative_pronouns = {
            "nom": "der",
            "acc": "den",
            "dat": "dem",
            "gen": "dessen",
        }
    elif gender == "w":
        definite = {
            "nom": "die Patientin",
            "acc": "die Patientin",
            "dat": "der Patientin",
            "gen": "der Patientin",
        }
        indefinite = {
            "nom": "eine Patientin",
            "acc": "eine Patientin",
            "dat": "einer Patientin",
            "gen": "einer Patientin",
        }
        plural = "Patientinnen"
        compound_stem = "Patientinnen"
        base = "Patientin"
        relative_pronouns = {
            "nom": "die",
            "acc": "die",
            "dat": "der",
            "gen": "deren",
        }
    else:
        definite = {
            "nom": "die Patientin oder der Patient",
            "acc": "die Patientin oder den Patienten",
            "dat": "der Patientin oder dem Patienten",
            "gen": "der Patientin oder des Patienten",
        }
        indefinite = {
            "nom": "eine Patientin oder ein Patient",
            "acc": "eine Patientin oder einen Patienten",
            "dat": "einer Patientin oder einem Patienten",
            "gen": "einer Patientin oder eines Patienten",
        }
        plural = "Patientinnen oder Patienten"
        compound_stem = "Patient:innen"
        base = "Patient:in"
        relative_pronouns = {
            "nom": "die",
            "acc": "die",
            "dat": "denen",
            "gen": "deren",
        }

    return PatientForms(
        definite=definite,
        indefinite=indefinite,
        plural=plural,
        compound_stem=compound_stem,
        base=base,
        relative_pronouns=relative_pronouns,
    )
