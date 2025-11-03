"""Zentrale Paketmarkierung für die Modul-Sammlung von Karina-Chat."""

# Hinweis: Das Anlegen dieser Datei verhindert, dass Python das Verzeichnis
# versehentlich als Namespace-Paket mit gleichnamigen Drittanbieter-Paketen
# zusammenführt. Dadurch bleiben unsere eigenen Untermodule wie
# ``module.mcp_client`` zuverlässig importierbar.

# Dokumentation zum Entfernen der Providerverwaltung:
# --------------------------------------------------
# Die frühere dynamische Auswahl des LLM-Providers wurde komplett entfernt,
# damit keine veralteten Streamlit-States mehr geladen werden. Sollte zukünftig
# wieder eine Providerverwaltung erforderlich sein, kann dafür die ehemals unter
# ``module/llm_state.py`` liegende Hilfslogik erneut eingeführt oder aus der
# Versionsverwaltung wiederhergestellt werden. Anschließend lässt sich die
# Streamlit-Session-State-Initialisierung beispielsweise über einen separaten
# Initialisierungsschritt (z. B. in ``module/sidebar.py``) aktivieren, indem
# dort die gewünschten Provider-Konstanten gesetzt und bei Bedarf UI-Elemente
# zum Umschalten eingeblendet werden. Für Debugging-Zwecke kann man
# zusätzlich eine Logging-Ausgabe aktivieren, die den aktuell geladenen
# Provider beim App-Start protokolliert.

__all__: list[str] = []
