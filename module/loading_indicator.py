"""Visualisiert parallele Aufgabenlisten während Streamlit-Spins.

Das Modul stellt eine kleine Hilfsbibliothek bereit, um neben dem klassischen
``st.spinner`` gleichzeitig konkrete Arbeitsschritte in kleiner Schrift sowie
einen Fortschrittsbalken zu zeigen. Die Nutzer erhalten dadurch transparenten
Einblick, welche Teilaufgaben während einer Wartezeit abgearbeitet werden. Für
die Entwicklung ist ein optionaler Debug-Schalter vorgesehen, der zusätzliche
Statusinformationen im Streamlit-Frontend anzeigt.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable, List

import streamlit as st

# Debug-Schalter für Entwickler: Bei Bedarf auf ``True`` setzen, um zusätzliche
# Informationen über ``st.write`` auszugeben und die Fortschrittsberechnung
# nachzuvollziehen. So lassen sich bei Bedarf Timing-Probleme oder fehlende
# Fortschrittsaktualisierungen leichter eingrenzen.
DEBUG_TASK_PROGRESS = False


@dataclass
class _TaskState:
    """Verwaltet Fortschritt und Abschlussstatus der einzelnen Mini-Aufgaben."""

    tasks: List[str]
    current_index: int = 0
    completed: bool = False

    def advance(self, steps: int = 1) -> None:
        """Schaltet auf die nächste Aufgabe weiter und setzt den Status."""

        if self.completed:
            return
        self.current_index = min(len(self.tasks), self.current_index + steps)
        self.completed = self.current_index >= len(self.tasks)

    @property
    def ratio(self) -> float:
        """Gibt den aktuellen Bearbeitungsstand als Verhältnis zurück."""

        if not self.tasks:
            return 1.0
        return min(1.0, self.current_index / len(self.tasks))


class TaskProgressDisplay:
    """Kapselt die visuelle Darstellung der Fortschrittsliste samt Balken.

    Die Klasse erzeugt intern zwei Platzhalter: einen Streamlit-Progress-Balken
    sowie eine HTML-formatierte Liste in kleiner Schrift. Die Methode
    :meth:`advance` aktualisiert beide Komponenten synchron, sodass jederzeit
    ersichtlich ist, welche Aufgabe gerade bearbeitet wird.
    """

    def __init__(
        self,
        tasks: Iterable[str],
        progress_container: "st.delta_generator.DeltaGenerator",
        text_container: "st.delta_generator.DeltaGenerator",
        debug_container: "st.delta_generator.DeltaGenerator | None" = None,
    ):
        # Die Container werden von ``task_spinner`` in der gewünschten Reihenfolge
        # vorbereitet, damit im Interface zuerst der Spinner, dann der Fortschritts-
        # balken und anschließend die Detailtexte erscheinen. Durch das Injizieren
        # der Platzhalter bleibt die Darstellungsreihenfolge flexibel.
        self._state = _TaskState(list(tasks))
        self._progress_container = progress_container
        self._text_container = text_container
        self._debug_container = debug_container
        self._progress_bar = self._progress_container.progress(0.0)
        self._render()

    def _render(self) -> None:
        """Aktualisiert Progressbar und Textanzeige auf Basis des aktuellen Status."""

        ratio = self._state.ratio
        try:
            self._progress_bar.progress(ratio)
        except TypeError:
            # Streamlit-Versionen < 1.20 erlauben keine Floats; daher wird eine
            # prozentuale Umrechnung vorgenommen.
            self._progress_bar.progress(int(ratio * 100))
        lines = []
        for index, task in enumerate(self._state.tasks):
            if index < self._state.current_index:
                symbol = "✅"
            elif index == self._state.current_index and not self._state.completed:
                symbol = "🔄"
            else:
                symbol = "⏳"
            lines.append(
                f"<div style='font-size:0.75rem'>{symbol} {task}</div>"
            )
        if not lines:
            lines.append("<div style='font-size:0.75rem'>⏳ Vorbereitung läuft...</div>")
        self._text_container.markdown("".join(lines), unsafe_allow_html=True)
        if self._debug_container is not None:
            self._debug_container.write({
                "ratio": ratio,
                "current_index": self._state.current_index,
                "completed": self._state.completed,
            })

    def advance(self, steps: int = 1) -> None:
        """Markiert Aufgaben als erledigt und zeigt den Fortschritt an."""

        self._state.advance(steps)
        self._render()

    def complete(self) -> None:
        """Schließt alle Aufgaben ab und zeigt einen vollen Fortschrittsbalken."""

        self._state.current_index = len(self._state.tasks)
        self._state.completed = True
        self._render()

    def cleanup(self) -> None:
        """Entfernt temporäre Platzhalter nach Abschluss der Aufgabe."""

        self._progress_container.empty()
        self._text_container.empty()
        if self._debug_container is not None:
            self._debug_container.empty()


@contextmanager
def task_spinner(spinner_text: str, tasks: Iterable[str]):
    """Kombiniert Streamlit-Spinner, Aufgabenliste und Fortschrittsbalken.

    Die Funktion dient als Kontextmanager. Innerhalb des ``with``-Blocks können
    Aufrufer über :meth:`TaskProgressDisplay.advance` einzelne Schritte als
    abgeschlossen markieren. Nach Verlassen des Blocks werden Progressbar und
    Hilfstexte automatisch aufgeräumt.
    """

    # Die Ausgabeelemente werden bewusst in dieser Reihenfolge erzeugt, damit im
    # Streamlit-Frontend erst der Spinner sichtbar wird, anschließend der Balken
    # und zuletzt die Detailtexte. Entwickelnde können bei Bedarf zusätzliche
    # Container einfügen (z. B. ``st.container()``), solange sie diese Reihenfolge
    # beibehalten.
    spinner_placeholder = st.empty()
    progress_placeholder = st.empty()
    text_placeholder = st.empty()
    debug_placeholder = st.empty() if DEBUG_TASK_PROGRESS else None

    display = TaskProgressDisplay(
        tasks,
        progress_container=progress_placeholder,
        text_container=text_placeholder,
        debug_container=debug_placeholder,
    )
    try:
        with spinner_placeholder.spinner(spinner_text):
            yield display
    finally:
        display.complete()
        display.cleanup()
