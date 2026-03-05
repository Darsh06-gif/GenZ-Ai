from __future__ import annotations

import streamlit as st


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>
          /* Layout */
          .block-container { padding-top: 1.25rem; padding-bottom: 2.5rem; }
          [data-testid="stSidebar"] { border-right: 1px solid rgba(148,163,184,0.18); }

          /* Typography */
          h1, h2, h3 { letter-spacing: -0.02em; }
          .muted { color: rgba(229,231,235,0.70); }

          /* Inputs */
          [data-testid="stTextInput"] input,
          [data-testid="stTextArea"] textarea { border-radius: 12px; }

          /* Buttons */
          .stButton>button { border-radius: 12px; padding: 0.55rem 0.9rem; }

          /* Cards */
          .card {
            border: 1px solid rgba(148,163,184,0.18);
            background: rgba(17,27,46,0.55);
            border-radius: 16px;
            padding: 1rem 1rem;
          }
          .card strong { color: rgba(229,231,235,0.95); }
          .card small { color: rgba(229,231,235,0.70); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, subtitle: str | None = None) -> None:
    st.markdown(
        f"""
        <div class="card">
          <div style="font-size: 0.95rem; font-weight: 650;">{title}</div>
          {f'<div class="muted" style="margin-top: 0.25rem; font-size: 0.85rem;">{subtitle}</div>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )

