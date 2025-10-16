"""Zentrale Paketmarkierung für die Modul-Sammlung von Karina-Chat."""

# Hinweis: Das Anlegen dieser Datei verhindert, dass Python das Verzeichnis
# versehentlich als Namespace-Paket mit gleichnamigen Drittanbieter-Paketen
# zusammenführt. Dadurch bleiben unsere eigenen Untermodule wie
# ``module.mcp_client`` zuverlässig importierbar.

__all__: list[str] = []
