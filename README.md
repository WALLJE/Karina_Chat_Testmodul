<!-- HINWEIS: Diese README wurde umfassend dokumentiert, damit neue Administratorinnen und Administratoren den Aufbau der Anwendung schnell nachvollziehen können. -->
# Karina-Chat

## Inhaltsverzeichnis
1. [Überblick](#überblick)
2. [Systemvoraussetzungen](#systemvoraussetzungen)
3. [Installation](#installation)
4. [Starten der Anwendung](#starten-der-anwendung)
5. [Grundlegende Nutzung](#grundlegende-nutzung)
6. [Admin-Modus](#admin-modus)
    1. [Anmeldung](#anmeldung)
    2. [Verwaltung von Fallbeispielen](#verwaltung-von-fallbeispielen)
    3. [Feedback- und Befundmodule](#feedback--und-befundmodule)
    4. [Diagnostische Funktionen](#diagnostische-funktionen)
    5. [Debugging-Hilfen](#debugging-hilfen)
7. [Fehlerbehebung](#fehlerbehebung)
8. [Weiterführende Ressourcen](#weiterführende-ressourcen)

## Überblick
Der Karina-Chat unterstützt medizinische Ausbildungsszenarien, indem realistische Patientinnen- und Patientengespräche simuliert werden. Nutzerinnen und Nutzer können zwischen verschiedenen Modulen (z. B. Sprach-, Feedback- oder Befundmodul) wechseln. Diese README fokussiert sich darauf, die wichtigsten Bedienwege zu erläutern.

<!-- Tipp: Dieser Abschnitt kann bei Bedarf erweitert werden, falls neue Module hinzukommen. -->

## Systemvoraussetzungen
- Python 3.10 oder neuer
- Virtuelle Umgebung (empfohlen)
- Abhängigkeiten aus `requirements.txt`
- Optional: Zugriff auf Streamlit-Frontend (bereits vorkonfiguriert und muss nicht separat getestet werden)

## Installation
1. Repository klonen:
   ```bash
   git clone <REPOSITORY-URL>
   cd Karina_Chat_Testmodul
   ```
2. Virtuelle Umgebung erstellen und aktivieren:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
3. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```

## Starten der Anwendung
1. Sicherstellen, dass die virtuelle Umgebung aktiv ist.
2. Streamlit-Anwendung starten:
   ```bash
   streamlit run Karina_Chat_2.py
   ```
3. Die Oberfläche ist anschließend über den lokal ausgegebenen Link erreichbar.

<!-- Hinweis: Bei Deployment auf einem Server können hier spezifische Schritte ergänzt werden. -->

## Grundlegende Nutzung
- **Modulauswahl:** Über das Seitenmenü lassen sich die verschiedenen Module aufrufen (z. B. Sprach-, Befund- oder Feedbackmodul).
- **Interaktion:** Dialoge werden Schritt für Schritt geführt. Eingaben können über Textfelder oder vordefinierte Auswahlmöglichkeiten erfolgen.
- **Speicherung:** Relevante Eingaben werden intern abgelegt, sodass ein Wechsel zwischen Modulen ohne Datenverlust möglich ist.

## Admin-Modus
Der Admin-Modus ermöglicht es befugten Personen, Inhalte und Konfigurationen des Systems anzupassen. Im Folgenden werden die wichtigsten Funktionen erläutert.

### Anmeldung
- **Zugang:** Der Admin-Modus wird über den entsprechenden Menüpunkt oder eine Tastenkombination aktiviert. Standardmäßig ist ein Passwortschutz vorgesehen.
- **Berechtigungen:** Nach erfolgreicher Anmeldung stehen administrative Werkzeuge zur Verfügung, die nur Lesenden mit Administratorrechten zugänglich sind.

### Verwaltung von Fallbeispielen
- **Import & Export:** Fallbeispiele können über die Admin-Oberfläche importiert (z. B. aus `fallbeispiele.xlsx`) oder als Sicherung exportiert werden.
- **Bearbeitung:** Einzelne Fälle lassen sich duplizieren, editieren und archivieren. Änderungen werden sofort gespeichert.
- **Validierung:** Eingebettete Prüfmechanismen verhindern inkonsistente Datensätze und geben bei Bedarf deutschsprachige Fehlermeldungen aus.

### Feedback- und Befundmodule
- **Konfiguration:** Administratorinnen und Administratoren können Feedbackregeln anpassen und neue Befundvorlagen hinzufügen.
- **Überwachung:** Es gibt Einsicht in Bewertungsverläufe, sodass Ausbildungsfortschritte nachvollzogen werden können.
- **Anpassung:** Schwellenwerte für automatische Bewertungen lassen sich konfigurieren, um unterschiedliche Ausbildungsniveaus zu berücksichtigen.

### Diagnostische Funktionen
- **Log-Ansicht:** Der Admin-Modus bietet Zugriff auf System-Logs, in denen Nutzerinteraktionen und Modulwechsel dokumentiert sind.
- **Diagnostikmodul:** Über das `diagnostikmodul.py` können gezielte Prüfungen von Patientengesprächen durchgeführt und Ergebnisse exportiert werden.
- **Fehlerprotokoll:** Administratoren können hier gezielt nach Auffälligkeiten suchen, um technische Probleme schneller zu identifizieren.

### Debugging-Hilfen
- **Deaktivierte Fallbacks:** Statt automatischer Fallbacks stehen kommentierte Debugging-Hilfen bereit. Diese können im Code aktiviert werden, um detaillierte Ausgaben zu erhalten.
- **Konfigurationsdateien:** Hinweise innerhalb der Module beschreiben, wie Debugging-Flags gesetzt werden können, ohne das Live-System zu beeinträchtigen.
- **Praxis-Tipp:** Vor jeder Aktivierung von Debugging-Hilfen sollte eine Sicherung der Konfiguration vorgenommen werden.

## Fehlerbehebung
- **Fehlende Abhängigkeiten:** Prüfen, ob `pip install -r requirements.txt` ohne Fehlermeldung durchlief.
- **Port-Konflikte:** Falls der Standardport von Streamlit bereits belegt ist, kann ein alternativer Port angegeben werden (`streamlit run Karina_Chat_2.py --server.port 8502`).
- **Authentifizierungsprobleme:** Zugangsdaten im Admin-Modus prüfen und bei Bedarf zurücksetzen.
- **Datenbank- oder Dateizugriff:** Sicherstellen, dass die benötigten Dateien (z. B. CSV oder Excel) vorhanden und nicht schreibgeschützt sind.

<!-- Debugging-Hinweis: Für tiefergehende Analysen kann das Logging-Level im Code angehoben werden. Die entsprechenden Stellen sind im Admin-Modus dokumentiert. -->

## Weiterführende Ressourcen
- Interne Dokumentation (Confluence/SharePoint)
- Ansprechpartnerin/Ansprechpartner im Entwicklungsteam
- Schulungsvideos und Onboarding-Materialien

Wir wünschen viel Erfolg bei der Arbeit mit dem Karina-Chat!
