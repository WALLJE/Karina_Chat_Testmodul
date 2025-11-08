from module.patient_language import get_patient_forms
from module.offline import (
    get_offline_koerperbefund,
    get_offline_sonderuntersuchung,
    is_offline,
)
from module.token_counter import init_token_counters, add_usage


def generiere_koerperbefund(client, diagnose_szenario, diagnose_features, koerper_befund_tip):
    if is_offline():
        return get_offline_koerperbefund()

    patient_forms = get_patient_forms()

    prompt = f"""
{patient_forms.phrase("nom", capitalize=True)} hat eine zufällig simulierte Erkrankung. Diese lautet: {diagnose_szenario}.
Weitere relevante anamnestische Hinweise: {diagnose_features}
Zusatzinformationen: {koerper_befund_tip}
Erstelle einen körperlicen Untersuchungsbefund, der zu dieser Erkrankung passt, ohne sie explizit zu nennen oder zu diagnostizieren. Berücksichtige Befunde, die sich aus den Zusatzinformationen ergeben könnten.
Erstelle eine klinisch konsistente Befundlage für die simulierte Erkrankung. Interpretiere die Befunde nicht, gib keine Hinweise auf die Diagnose.

Beginne immer mit zwei Vitalparametern in eigenen Zeilen:
Blutdruck: <systolisch>/<diastolisch> mmHg
Herzfrequenz: <Wert>/Minute

Strukturiere den anschließenden Befund in folgende Abschnitte:

**Allgemeinzustand:**
**Abdomen:**
**Auskultation Herz/Lunge:**
**Haut:**
**Extremitäten:**

Gib ausschließlich körperliche Untersuchungsbefunde an – keine Bildgebung, Labordiagnostik oder Zusatzverfahren. Vermeide jede Form von Bewertung, Hypothese oder Krankheitsnennung.

Formuliere neutral, präzise und sachlich – so, wie es in einem klinischen Untersuchungsprotokoll stehen würde.
"""

    # Vor dem API-Aufruf initialisieren wir die Token-Zähler, damit auch bei parallelen Aufrufen
    # keine leeren Strukturen entstehen und die Summen konsistent bleiben.
    init_token_counters()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    # Damit der Tokenverbrauch jederzeit nachvollziehbar bleibt, addieren wir ihn direkt.
    # Auch hier gilt: "total_tokens" beschreibt nur diesen einen Call; durch das fortlaufende
    # Aufsummieren halten wir eine gesamt Sitzungssumme bereit. Für Detailanalysen können bei
    # Bedarf ergänzende Debug-Ausgaben aktiviert werden.
    add_usage(
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens,
    )
    return response.choices[0].message.content.strip()


def generiere_sonderuntersuchung(
    client,
    diagnose_szenario: str,
    diagnose_features: str,
    sonderwunsch: str,
    bestehender_befund: str,
) -> str:
    """Generiert eine fokussierte Ergänzung für eine gezielt angeforderte Untersuchung."""
    # Offline liefern wir einen eindeutigen Platzhalter zurück, damit auch ohne KI
    # nachvollziehbar bleibt, welche Zusatzuntersuchung gewünscht wurde.
    if is_offline():
        return get_offline_sonderuntersuchung(sonderwunsch)

    patient_forms = get_patient_forms()
    # Wir zwingen das Modell über die Prompt-Struktur zu knappen Stichpunkten,
    # damit die Supabase-Auswertung später keine Fließtexte, sondern klar
    # identifizierbare Befundfragmente enthält. Bei Bedarf können Entwicklerinnen
    # und Entwickler die Stichpunktzahl erhöhen, indem sie weitere Bullet-Punkte
    # aktivieren – entsprechende Hinweise stehen im Prompt.
    prompt = f"""
{patient_forms.phrase("nom", capitalize=True)} weist die simulierte Erkrankung "{diagnose_szenario}" auf.
Wichtige anamnestische Hinweise: {diagnose_features}
Bereits vorliegender Untersuchungsbefund:
{bestehender_befund}

Die folgende zusätzliche körperliche Untersuchung wurde explizit angefordert:
{sonderwunsch}
Formuliere ein kompaktes, stichwortartiges Untersuchungsergebnis.

Gib ausschließlich körperliche Untersuchungsbefunde an. Keine Diagnosen, kein Ausblick.
"""

    init_token_counters()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    add_usage(
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens,
    )
    return response.choices[0].message.content.strip()
