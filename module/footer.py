"""Hilfsfunktionen für die Fußzeile der Anwendung."""

import streamlit as st

from module.fall_config import get_behavior_fix_state, get_fall_fix_state


def copyright_footer() -> None:
    """Rendert die Fußzeile mit Hinweisen zum Fixierungsstatus."""

    fall_fixed, _ = get_fall_fix_state()
    behavior_fixed, _ = get_behavior_fix_state()

    if fall_fixed:
        fall_status_text = "Fallstatus: Fixiert"
        fall_status_class = "fixed"
    else:
        fall_status_text = "Fallstatus: Zufällig"
        fall_status_class = "random"

    if behavior_fixed:
        behavior_status_text = "Verhaltensstatus: Fixiert"
        behavior_status_class = "fixed"
    else:
        behavior_status_text = "Verhaltensstatus: Zufällig"
        behavior_status_class = "random"

    # Hinweis: Für Debugging lässt sich hier bei Bedarf ein `print` der beiden Statusvariablen aktivieren.
    # Die nachfolgende CSS-Definition sorgt für eine zweizeilige Darstellung der Fußzeile,
    # bei der in der ersten Zeile der allgemeine Hinweis und in der zweiten Zeile beide Statuswerte
    # gemeinsam im Format "Fallstatus: ... - Verhaltensstatus: ..." ausgegeben werden.
    st.markdown(
        f"""
        <style>
        .footer {{
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: #f1f1f1;
            color: #666;
            text-align: center;
            padding: 8px;
            font-size: 0.85em;
            border-top: 1px solid #ddd;
            z-index: 100;
        }}
        .footer .statusbereich {{
            display: block;
            margin-top: 6px;
            font-weight: 600;
        }}
        .footer .statusbereich .status-zeile {{
            color: #c0392b;
        }}
        .footer .statusbereich .status-zeile.random {{
            color: #666;
        }}
        .footer .statusbereich .trenner {{
            color: #666;
        }}
        </style>
        <div class="footer">
            <div class="footer-hinweis">&copy; 2025 – Diese Simulation dient ausschließlich zu Lehrzwecken.</div>
            <div class="statusbereich">
                <span class="status-zeile {fall_status_class}">{fall_status_text}</span>
                <span class="trenner"> - </span>
                <span class="status-zeile {behavior_status_class}">{behavior_status_text}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
