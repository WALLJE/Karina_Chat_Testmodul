<!-- HINWEIS: Diese README wurde umfassend dokumentiert, damit neue Administratorinnen und Administratoren den Aufbau der Anwendung schnell nachvollziehen können. -->
# Karina-Chat

## Inhaltsverzeichnis
1. [Überblick](#überblick)
2. [Systemvoraussetzungen](#systemvoraussetzungen)
3. [Installation](#installation)
4. [Starten der Anwendung](#starten-der-anwendung)
5. [Grundlegende Nutzung](#grundlegende-nutzung)
    1. [Automatisches Zurücksetzen bei Direktaufrufen](#automatisches-zurücksetzen-bei-direktaufrufen)
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
- **Startseite als Einstieg:** `Karina_Chat_2.py` dient ausschließlich der Fallvorbereitung und führt nach Bestätigung der Instruktionen automatisch zur ersten Seite der Multipage-App.
- **Interaktion:** Dialoge werden Schritt für Schritt geführt. Eingaben können über Textfelder oder vordefinierte Auswahlmöglichkeiten erfolgen.
- **Speicherung:** Relevante Eingaben werden intern abgelegt, sodass ein Wechsel zwischen Modulen ohne Datenverlust möglich ist.

### Neustart nach der Evaluation
- **Button „🔄 Neues Szenario starten“:** Nach Abschluss der Evaluation erscheint am unteren Seitenrand ein klar erkennbarer Button. Ein Klick darauf leert alle fallbezogenen Angaben (z. B. Chatverlauf, Befunde, diagnostische Entscheidungen) und setzt die Startinstruktionen zurück.
- **Automatisch frisches Szenario:** Beim Klick merken wir uns das gerade abgeschlossene Szenario. Bei der nächsten Auswahl wird es übersprungen, bis alle Fälle einmal gespielt wurden. Erst wenn die Liste erschöpft ist, wird sie automatisch geleert, sodass der Zufallszug wieder aus dem kompletten Pool erfolgen kann.
- **Sauberer Neustart:** Direkt im Anschluss leitet die Anwendung automatisch mit `st.switch_page("Karina_Chat_2.py")` zur Startseite. Dort läuft die Fallvorbereitung erneut durch, damit keine Datenreste aus der vorherigen Sitzung sichtbar bleiben.
- **Debugging-Hinweis:** Sollte der Reset ausnahmsweise nicht greifen, kann auf der Evaluationsseite kurzfristig `st.write(st.session_state)` aktiviert werden. So lassen sich verbleibende Schlüssel identifizieren und gezielt entfernen.

### Automatisches Zurücksetzen bei Direktaufrufen
- **Direkte Aufrufe werden abgefangen:** Wenn Nutzerinnen oder Nutzer versuchen, eine Unterseite ohne vorbereiteten Fall direkt
  über die URL zu öffnen, leitet die Anwendung automatisch zur Startseite zurück.
- **Hinweis auf der Startseite:** Die ausgelöste Unterseite hinterlegt einen Hinweistext im `st.session_state`. Beim nächsten
  Laden zeigt die Startseite diesen Warnhinweis einmalig an und entfernt ihn anschließend wieder, damit keine veralteten Meldungen
  sichtbar bleiben.
- **Debugging-Tipp:** Für Fehlersuchen kann der Session-State über `st.write(st.session_state)` ausgegeben werden. Die Stelle ist
  im Startskript kommentiert, sodass die zusätzliche Ausgabe bei Bedarf schnell aktiviert werden kann.

## Admin-Modus
Der Admin-Modus ermöglicht es befugten Personen, Inhalte und Konfigurationen des Systems anzupassen. Im Folgenden werden die wichtigsten Funktionen erläutert.

### Anmeldung
- **Zugang:** Der Admin-Modus wird über den entsprechenden Menüpunkt oder eine Tastenkombination aktiviert. Standardmäßig ist ein Passwortschutz vorgesehen.
- **Berechtigungen:** Nach erfolgreicher Anmeldung stehen administrative Werkzeuge zur Verfügung, die nur Lesenden mit Administratorrechten zugänglich sind.

### Verwaltung von Fallbeispielen
- **Zentrales Datenmodell:** Sämtliche Szenarien liegen in der Supabase-Tabelle `fallbeispiele`. Der Adminbereich lädt die Inhalte direkt aus dieser Quelle und verzichtet vollständig auf die bisherige Excel-Datei.
- **SQL-Beispiel:** Die folgende Definition kann in der Supabase-SQL-Konsole ausgeführt werden und legt die Tabelle inklusive Trigger für automatische Zeitstempel an:

```sql
create table if not exists public.fallbeispiele (
    id bigint generated by default as identity primary key,
    szenario text not null unique,
    beschreibung text not null,
    koerperliche_untersuchung text not null,
    besonderheit text,
    alter integer,
    geschlecht text check (geschlecht in ('m', 'w', 'n')),
    amboss_input text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create trigger set_fallbeispiele_updated_at
    before update on public.fallbeispiele
    for each row
    execute function public.set_updated_at();
```

- **Hinweis zur Trigger-Funktion:** Supabase liefert mit jeder neuen Datenbank die Funktion `public.set_updated_at()`. Falls sie entfernt wurde, kann sie wie folgt wiederhergestellt werden:

```sql
create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$ language plpgsql;
```
- **Bearbeitung:** Neue Fälle werden im Admin-Formular erfasst und landen unmittelbar in Supabase. Über denselben Weg lassen sich bestehende Szenarien aktualisieren oder löschen (z. B. via Supabase-Konsole).
- **AMBOSS-Input verwalten:** Die Spalte `amboss_input` speichert je Szenario die komprimierte AMBOSS-Zusammenfassung. Der Adminbereich erlaubt, zwischen dauerhaftem MCP-Abruf, Abruf nur bei leeren Feldern oder einem zufälligen Refresh (mit einstellbarer Wahrscheinlichkeit) zu wechseln.
- **Statuskontrolle:** Während der Fallvorbereitung zeigt der Spinner explizit an, dass der AMBOSS-Text geprüft und bei Bedarf gespeichert wird. Im Adminbereich erscheint anschließend eine Statusmeldung, ob das Supabase-Feld aktualisiert wurde oder aus welchen Gründen der Schritt übersprungen wurde (z. B. Zufallsmodus, Override, Fehler).
- **Persistente Admin-Einstellungen:** Fixierungen für Szenario, Verhalten sowie der bevorzugte AMBOSS-Abrufmodus werden dauerhaft in der Supabase-Tabelle `fall_persistenzen` gespeichert. Der Adminbereich stellt die jeweils aktiven Werte in einem ausklappbaren Abschnitt dar.

### Feedback- und Befundmodule
- **Konfiguration:** Administratorinnen und Administratoren können Feedbackregeln anpassen und neue Befundvorlagen hinzufügen.
- **Überwachung:** Es gibt Einsicht in Bewertungsverläufe, sodass Ausbildungsfortschritte nachvollzogen werden können.
- **Anpassung:** Schwellenwerte für automatische Bewertungen lassen sich konfigurieren, um unterschiedliche Ausbildungsniveaus zu berücksichtigen.
- **Frühe Modusbestimmung:** Der aktive Feedback-Modus wird bereits beim Start festgelegt, damit der Adminbereich sofort den tatsächlichen Status ausweist.

### Diagnostische Funktionen
- **Log-Ansicht:** Der Admin-Modus bietet Zugriff auf System-Logs, in denen Nutzerinteraktionen und Modulwechsel dokumentiert sind.
- **Diagnostikmodul:** Über das `diagnostikmodul.py` können gezielte Prüfungen von Patientengesprächen durchgeführt und Ergebnisse exportiert werden.
- **Fehlerprotokoll:** Administratoren können hier gezielt nach Auffälligkeiten suchen, um technische Probleme schneller zu identifizieren.

### Debugging-Hilfen
- **Deaktivierte Fallbacks:** Statt automatischer Fallbacks stehen kommentierte Debugging-Hilfen bereit. Diese können im Code aktiviert werden, um detaillierte Ausgaben zu erhalten.
- **Supabase-Persistenz prüfen:** Für detaillierte Analysen lässt sich die Tabelle `fall_persistenzen` direkt in Supabase öffnen. Zusätzlich zeigt der Adminbereich alle gespeicherten Werte in strukturierter Form an.
- **Praxis-Tipp:** Vor jeder Aktivierung von Debugging-Hilfen sollte eine Sicherung der Konfiguration vorgenommen werden.

## Fehlerbehebung
- **Fehlende Abhängigkeiten:** Prüfen, ob `pip install -r requirements.txt` ohne Fehlermeldung durchlief.
- **Port-Konflikte:** Falls der Standardport von Streamlit bereits belegt ist, kann ein alternativer Port angegeben werden (`streamlit run Karina_Chat_2.py --server.port 8502`).
- **Authentifizierungsprobleme:** Zugangsdaten im Admin-Modus prüfen und bei Bedarf zurücksetzen.
- **Datenbank- oder Dateizugriff:** Prüfen, ob die Supabase-Tabellen (`fallbeispiele`, `fall_persistenzen` usw.) erreichbar sind und ob der verwendete API-Key Schreibrechte besitzt. Optional lokal genutzte Dateien (z. B. CSV für Namenslisten) sollten ebenfalls vorhanden und beschreibbar sein.

<!-- Debugging-Hinweis: Für tiefergehende Analysen kann das Logging-Level im Code angehoben werden. Die entsprechenden Stellen sind im Admin-Modus dokumentiert. -->

## Weiterführende Ressourcen
- Interne Dokumentation (Confluence/SharePoint)
- Ansprechpartnerin/Ansprechpartner im Entwicklungsteam
- Schulungsvideos und Onboarding-Materialien

Wir wünschen viel Erfolg bei der Arbeit mit dem Karina-Chat!
