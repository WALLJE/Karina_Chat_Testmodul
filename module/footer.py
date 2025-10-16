import streamlit as st

from module.fall_config import get_fall_fix_state


def copyright_footer():
    fixed, scenario = get_fall_fix_state()
    if fixed and scenario:
        status_text = "Fixierter Fall"
        status_class = "fixed"
    else:
        status_text = "Zufälliger Fall"
        status_class = "random"

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
        .footer .fall-status {{
            display: block;
            margin-top: 4px;
            font-weight: 600;
            color: #c0392b;
        }}
        .footer .fall-status.random {{
            color: #666;
        }}
        </style>
        <div class="footer">
            &copy; 2025 – Diese Simulation dient ausschließlich zu Lehrzwecken.
            <span class="fall-status {status_class}">{status_text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
