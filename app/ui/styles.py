from __future__ import annotations

import streamlit as st


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>

        /* ---------- GLOBAL BACKGROUND ---------- */

        .stApp {
            background: radial-gradient(circle at 20% 20%, rgba(56,189,248,0.25), transparent 40%),
                        radial-gradient(circle at 80% 30%, rgba(168,85,247,0.25), transparent 40%),
                        radial-gradient(circle at 40% 80%, rgba(34,197,94,0.20), transparent 40%),
                        linear-gradient(120deg, #0f172a, #020617);
            background-attachment: fixed;
        }

        /* subtle animated glow */
        .stApp::before {
            content: "";
            position: fixed;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 60%);
            animation: glowMove 18s linear infinite;
            z-index: 0;
        }

        @keyframes glowMove {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }


        /* ---------- LAYOUT ---------- */

        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
            max-width: 1200px;
        }

        [data-testid="stSidebar"] {
            background: rgba(2,6,23,0.65);
            backdrop-filter: blur(14px);
            border-right: 1px solid rgba(148,163,184,0.18);
        }


        /* ---------- TYPOGRAPHY ---------- */

        h1, h2, h3 {
            letter-spacing: -0.02em;
            font-weight: 650;
        }

        .muted {
            color: rgba(229,231,235,0.65);
        }


        /* ---------- INPUT FIELDS ---------- */

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea {
            border-radius: 12px;
            border: 1px solid rgba(148,163,184,0.20);
            background: rgba(15,23,42,0.65);
            backdrop-filter: blur(6px);
            transition: all 0.2s ease;
        }

        [data-testid="stTextInput"] input:focus,
        [data-testid="stTextArea"] textarea:focus {
            border: 1px solid rgba(99,102,241,0.7);
            box-shadow: 0 0 12px rgba(99,102,241,0.35);
        }


        /* ---------- BUTTONS ---------- */

        .stButton > button {
            border-radius: 12px;
            padding: 0.6rem 1rem;
            border: 1px solid rgba(99,102,241,0.4);
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            color: white;
            font-weight: 600;
            transition: all 0.25s ease;
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 0 14px rgba(99,102,241,0.65);
        }


        /* ---------- CARDS ---------- */

        .card {
            border: 1px solid rgba(148,163,184,0.18);
            background: rgba(17,27,46,0.55);
            backdrop-filter: blur(14px);
            border-radius: 16px;
            padding: 1rem 1rem;
            transition: all 0.25s ease;
            position: relative;
            overflow: hidden;
        }

        .card::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(120deg, transparent, rgba(99,102,241,0.25), transparent);
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .card:hover::before {
            opacity: 1;
        }

        .card:hover {
            transform: translateY(-3px);
            border: 1px solid rgba(99,102,241,0.4);
            box-shadow: 0 0 20px rgba(99,102,241,0.25);
        }

        .card strong {
            color: rgba(229,231,235,0.95);
        }

        .card small {
            color: rgba(229,231,235,0.70);
        }

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
