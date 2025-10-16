import streamlit as st
from module.token_counter import init_token_counters, add_usage
from module.offline import get_offline_sprachcheck, is_offline

def sprach_check(text_input, client):
    if not text_input.strip():
        return ""

    if is_offline():
        return get_offline_sprachcheck(text_input)

    prompt = f"""
Bitte überprüfe die folgenden stichpunktartigen medizinischen Fachbegriffe hinsichtlich Orthographie und Zeichensetzung, schreibe Abkürzungen aus.
Gib den korrigierten Text direkt und ohne Vorbemerkung und ohne Kommentar zurück.
*Stichpunkte*
Gib stichpunktartige Begriffe bitte **mit je einem Zeilenumbruch pro Eintrag** in folgendem Format zurück:

- Begriff 1  
- Begriff 2  
- Begriff 3

⚠️ Verwende für jeden Stichpunkt eine **eigene Zeile mit einem Spiegelstrich (-)**. Niemals mehrere Begriffe in einer Zeile.

*Freier Text*
Freie Texte wie Therapiebegründungen werden als sprachlich und grammatikalisch korrigierter Fließtext zurückgegeben und **ohne Spiegelstriche**.

Text:
{text_input}
"""

    try:
        init_token_counters()
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        korrigiert = response.choices[0].message.content.strip()
        # korrigiert = korrigiert.replace("- ", "• ") # zerschiesst das Format.
        add_usage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens
        )
        return korrigiert

    except Exception as e:
        st.error(f"Fehler bei GPT-Anfrage: {e}")
        return text_input
