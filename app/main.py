from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from app.core.answer import build_answer
from app.core.db import Db, db_conn, get_document, list_documents
from app.core.embeddings import Embedder
from app.core.ingest import ingest_pdf
from app.core.ocr import OcrSettings
from app.core.paths import get_paths
from app.core.retrieval import retrieve, retrieve_multi, should_answer
from app.core.text_clean import normalize_query
from app.ui.styles import inject_global_styles


st.set_page_config(
    page_title="Handwritten Notes Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _init_state() -> None:
    if "tesseract_cmd" not in st.session_state:
        st.session_state.tesseract_cmd = ""
    if "ocr_dpi" not in st.session_state:
        st.session_state.ocr_dpi = 300
    if "ocr_lang" not in st.session_state:
        st.session_state.ocr_lang = "eng"
    if "retrieval_top_k" not in st.session_state:
        st.session_state.retrieval_top_k = 8
    if "retrieval_lexical_pool" not in st.session_state:
        st.session_state.retrieval_lexical_pool = 80
    if "retrieval_min_score" not in st.session_state:
        st.session_state.retrieval_min_score = 0.12
    if "show_debug_scores" not in st.session_state:
        st.session_state.show_debug_scores = False
    if "selected_document_id" not in st.session_state:
        st.session_state.selected_document_id = ""


def _fmt_dt(s: str) -> str:
    try:
        # stored as ISO8601 with timezone
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s


def _chat_key(document_id: str) -> str:
    return f"chat:{document_id}"


def _scope_key(document_ids: list[str]) -> str:
    return "+".join(sorted(str(d) for d in document_ids if d))


def _get_chat(document_id: str) -> list[dict[str, object]]:
    key = _chat_key(document_id)
    if key not in st.session_state:
        st.session_state[key] = []
    return st.session_state[key]


def _reset_chat(document_id: str) -> None:
    st.session_state[_chat_key(document_id)] = []


def _sidebar_settings(paths: "object") -> str:
    with st.sidebar:
        st.markdown("### Handwritten Notes")
        st.caption("Offline OCR + search, with page-cited sources.")
        st.divider()

        page = st.radio(
            "Navigate",
            options=["Ask", "Upload", "Library", "Settings", "About"],
            label_visibility="collapsed",
            key="nav_page",
        )

        st.divider()
        with st.expander("Quick settings", expanded=(page in {"Ask", "Upload"})):
            st.session_state.tesseract_cmd = st.text_input(
                "Tesseract path (optional)",
                value=st.session_state.tesseract_cmd,
                help="Set full path to tesseract.exe if OCR can't find it.",
                placeholder=r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            )
            st.session_state.ocr_dpi = st.slider(
                "OCR DPI", min_value=150, max_value=400, value=int(st.session_state.ocr_dpi), step=50
            )
            st.session_state.ocr_lang = st.text_input(
                "OCR language(s)",
                value=str(st.session_state.ocr_lang),
                help="Tesseract language codes, e.g. 'eng' or 'eng+hin'.",
            )

        with st.expander("Retrieval", expanded=False):
            st.session_state.retrieval_top_k = st.slider(
                "Top results",
                min_value=3,
                max_value=15,
                value=int(st.session_state.retrieval_top_k),
                step=1,
            )
            st.session_state.retrieval_lexical_pool = st.slider(
                "Lexical candidate pool",
                min_value=30,
                max_value=200,
                value=int(st.session_state.retrieval_lexical_pool),
                step=10,
                help="Larger values can improve recall but may be slower.",
            )
            st.session_state.retrieval_min_score = st.slider(
                "Minimum answer confidence",
                min_value=0.01,
                max_value=0.50,
                value=float(st.session_state.retrieval_min_score),
                step=0.01,
                help="If the best match is below this score, the app will say it doesn't have enough information.",
            )
            st.session_state.show_debug_scores = st.toggle("Show scores in sources", value=bool(st.session_state.show_debug_scores))

        st.divider()
        st.caption(f"Data: `{Path(paths.data_dir).as_posix()}`")

    return page


def main() -> None:
    _init_state()
    inject_global_styles()
    paths = get_paths()
    db = Db(paths.db_path)
    db.migrate()

    page = _sidebar_settings(paths)

    st.markdown("## Handwritten Notes Assistant")
    st.markdown('<div class="muted">OCR handwritten PDFs locally, then ask questions with page-cited sources.</div>', unsafe_allow_html=True)
    st.write("")

    embedder = Embedder(dim=1024)

    if page == "Upload":
        st.markdown("### Upload & index")
        left, right = st.columns([1.2, 0.8], gap="large")
        with left:
            uploaded = st.file_uploader("PDF file", type=["pdf"], accept_multiple_files=False)
            display_name = st.text_input("Display name (optional)", placeholder="e.g. Linear Algebra — Week 3")

            if uploaded is not None:
                pdf_dir = paths.data_dir / "uploads"
                pdf_dir.mkdir(parents=True, exist_ok=True)
                pdf_path = pdf_dir / uploaded.name
                pdf_path.write_bytes(uploaded.getvalue())

                cache_dir = paths.data_dir / "cache" / pdf_path.stem
                st.caption(f"Saved locally to `{pdf_path}`")

                if st.button("Run OCR + Index", type="primary"):
                    settings = OcrSettings(
                        dpi=int(st.session_state.ocr_dpi),
                        lang=str(st.session_state.ocr_lang).strip() or "eng",
                        tesseract_cmd=(st.session_state.tesseract_cmd.strip() or None),
                    )
                    with st.spinner("Processing PDF (OCR can take a while)…"):
                        result = ingest_pdf(
                            db=db,
                            pdf_path=pdf_path,
                            display_name=display_name,
                            ocr_settings=settings,
                            embedder=embedder,
                            cache_images_dir=cache_dir,
                        )
                    st.success("Indexing complete.")
                    m1, m2 = st.columns(2)
                    m1.metric("Pages", result.pages)
                    m2.metric("Chunks", result.chunks)

        with right:
            st.markdown("#### Tips for better OCR")
            st.markdown(
                """
                - Use **300–350 DPI** for most handwriting.
                - Set correct **language(s)** if your notes mix scripts.
                - If OCR fails, paste the **full Tesseract path** in the sidebar.
                """
            )

    elif page == "Library":
        st.markdown("### Library")
        with db_conn(db) as conn:
            docs = list_documents(conn)

        if not docs:
            st.info("No documents indexed yet. Upload a PDF first.")
            return

        st.markdown('<div class="muted">Your notes stay local in the SQLite database under <code>data/</code>.</div>', unsafe_allow_html=True)
        st.write("")

        options = {f"{d['display_name']}  ·  {_fmt_dt(d['created_at'])}": d["id"] for d in docs}
        chosen = st.selectbox("Select a document", options=list(options.keys()))
        document_id = options[chosen]

        with db_conn(db) as conn:
            doc = get_document(conn, document_id)
        if doc is None:
            st.error("Document not found.")
            return

        c1, c2, c3 = st.columns([1.2, 1, 1], gap="large")
        with c1:
            st.markdown("#### Details")
            st.write(f"**Name:** {doc['display_name']}")
            st.write(f"**File:** `{doc['filename']}`")
            st.write(f"**Created:** {_fmt_dt(doc['created_at'])}")
            st.write(f"**ID:** `{doc['id']}`")
        with c2:
            st.markdown("#### Actions")
            if st.button("Start a new chat with this doc", type="primary"):
                st.session_state.selected_document_id = str(document_id)
                st.session_state.nav_page = "Ask"
                st.rerun()
            if st.button("Reset chat history for this doc"):
                _reset_chat(str(document_id))
                st.success("Chat reset.")
        with c3:
            st.markdown("#### Danger zone")
            confirm = st.checkbox("I understand this deletes the document and its index.")
            if st.button("Delete this document", disabled=not confirm):
                with db_conn(db) as conn:
                    conn.execute("DELETE FROM documents WHERE id=?", (str(document_id),))
                _reset_chat(str(document_id))
                st.success("Deleted.")
                st.rerun()

    elif page == "Settings":
        st.markdown("### Settings")
        st.markdown("#### OCR")
        st.session_state.tesseract_cmd = st.text_input(
            "Tesseract path (optional)",
            value=st.session_state.tesseract_cmd,
            placeholder=r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        )
        st.session_state.ocr_dpi = st.slider(
            "OCR DPI", min_value=150, max_value=400, value=int(st.session_state.ocr_dpi), step=50
        )
        st.session_state.ocr_lang = st.text_input(
            "OCR language(s)", value=str(st.session_state.ocr_lang), help="e.g. 'eng' or 'eng+hin'."
        )
        st.divider()
        st.markdown("#### Retrieval")
        st.session_state.retrieval_top_k = st.slider(
            "Top results", min_value=3, max_value=15, value=int(st.session_state.retrieval_top_k), step=1
        )
        st.session_state.retrieval_lexical_pool = st.slider(
            "Lexical candidate pool",
            min_value=30,
            max_value=200,
            value=int(st.session_state.retrieval_lexical_pool),
            step=10,
        )
        st.session_state.retrieval_min_score = st.slider(
            "Minimum answer confidence",
            min_value=0.01,
            max_value=0.50,
            value=float(st.session_state.retrieval_min_score),
            step=0.01,
        )
        st.session_state.show_debug_scores = st.toggle("Show scores in sources", value=bool(st.session_state.show_debug_scores))

    elif page == "About":
        st.markdown("### About")
        st.markdown(
            """
            **Handwritten Notes Assistant** is a local study companion:

            - OCRs handwritten PDFs page-by-page (offline)
            - Stores text + chunks in SQLite (FTS5)
            - Retrieves likely passages and answers with **page-cited sources**
            """
        )
        st.markdown('<div class="muted">No network calls are required after install.</div>', unsafe_allow_html=True)

    else:  # Ask
        with db_conn(db) as conn:
            docs = list_documents(conn)

        if not docs:
            st.info("Upload and index a PDF first.")
            return

        st.markdown("### Ask your notes")

        doc_labels = {f"{d['display_name']} ({d['id'][:12]}…)": d["id"] for d in docs}
        initial_label = None
        if st.session_state.selected_document_id:
            for label, did in doc_labels.items():
                if str(did) == str(st.session_state.selected_document_id):
                    initial_label = label
                    break

        ask_multi = st.toggle("Ask across multiple documents", value=False)
        if ask_multi:
            default_labels = [initial_label] if initial_label else [list(doc_labels.keys())[0]]
            chosen_labels = st.multiselect(
                "Choose notes",
                options=list(doc_labels.keys()),
                default=default_labels,
            )
            chosen_ids = [str(doc_labels[l]) for l in chosen_labels if l in doc_labels]
            if not chosen_ids:
                st.info("Select at least one document.")
                return
            scope = _scope_key(chosen_ids)
            document_id = chosen_ids[0]
            st.session_state.selected_document_id = document_id
        else:
            chosen_label = st.selectbox(
                "Choose notes",
                options=list(doc_labels.keys()),
                index=(list(doc_labels.keys()).index(initial_label) if initial_label in doc_labels else 0),
            )
            chosen_ids = [str(doc_labels[chosen_label])]
            scope = _scope_key(chosen_ids)
            document_id = chosen_ids[0]
            st.session_state.selected_document_id = document_id

        chat = _get_chat(scope)
        top_bar = st.columns([1, 1, 1.2])
        with top_bar[0]:
            if st.button("Reset chat"):
                _reset_chat(scope)
                st.rerun()
        with top_bar[1]:
            pass
        with top_bar[2]:
            st.markdown(
                '<div class="muted" style="text-align:right;">Tip: ask for definitions, summaries, or “where is X discussed?”</div>',
                unsafe_allow_html=True,
            )

        for m in chat:
            role = str(m.get("role", "assistant"))
            content = str(m.get("content", ""))
            with st.chat_message(role):
                st.write(content)
                sources = m.get("sources")
                if isinstance(sources, list) and sources:
                    with st.expander("Sources"):
                        for s in sources:
                            if not isinstance(s, dict):
                                continue
                            doc_name = s.get("document_name") or "Notes"
                            page_n = s.get("page_number")
                            excerpt = s.get("excerpt")
                            score = s.get("score")
                            if st.session_state.show_debug_scores and score is not None:
                                st.markdown(f"**{doc_name} · Page {page_n}**  ·  score `{float(score):.3f}`")
                            else:
                                st.markdown(f"**{doc_name} · Page {page_n}**")
                            st.write(str(excerpt))
                            st.divider()

        with st.expander("Add PDFs here", expanded=False):
            add_pdf = st.file_uploader("Add a PDF to your library", type=["pdf"], key="ask_add_pdf")
            add_name = st.text_input("Display name (optional)", key="ask_add_pdf_name")
            if add_pdf is not None:
                pdf_dir = paths.data_dir / "uploads"
                pdf_dir.mkdir(parents=True, exist_ok=True)
                pdf_path = pdf_dir / add_pdf.name
                pdf_path.write_bytes(add_pdf.getvalue())
                cache_dir = paths.data_dir / "cache" / pdf_path.stem
                if st.button("OCR + Index this PDF", type="primary", key="ask_add_pdf_btn"):
                    settings = OcrSettings(
                        dpi=int(st.session_state.ocr_dpi),
                        lang=str(st.session_state.ocr_lang).strip() or "eng",
                        tesseract_cmd=(st.session_state.tesseract_cmd.strip() or None),
                    )
                    with st.spinner("Processing PDF (OCR can take a while)…"):
                        result = ingest_pdf(
                            db=db,
                            pdf_path=pdf_path,
                            display_name=add_name,
                            ocr_settings=settings,
                            embedder=embedder,
                            cache_images_dir=cache_dir,
                        )
                    st.success("Added to library.")
                    st.session_state.selected_document_id = result.document_id
                    st.rerun()

        prompt = st.chat_input("Ask a question about your notes…")
        if prompt and normalize_query(prompt):
            chat.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Searching your notes…"):
                    with db_conn(db) as conn:
                        doc = get_document(conn, document_id)
                        if doc is None:
                            st.error("Document not found.")
                            return
                        qv = embedder.embed_query(prompt)
                        if len(chosen_ids) == 1:
                            hits = retrieve(
                                conn,
                                document_id=document_id,
                                query=prompt,
                                embedder_dim=embedder.dim,
                                query_vector=qv,
                                limit=int(st.session_state.retrieval_top_k),
                                lexical_pool=int(st.session_state.retrieval_lexical_pool),
                            )
                        else:
                            hits = retrieve_multi(
                                conn,
                                document_ids=chosen_ids,
                                query=prompt,
                                embedder_dim=embedder.dim,
                                query_vector=qv,
                                limit=int(st.session_state.retrieval_top_k),
                                lexical_pool=int(st.session_state.retrieval_lexical_pool),
                            )

                    if not should_answer(hits, min_score=float(st.session_state.retrieval_min_score)):
                        msg = "I don't have enough information in these notes."
                        st.warning(msg)
                        chat.append({"role": "assistant", "content": msg})
                        return

                    ans = build_answer(prompt, hits)
                    st.write(ans.text)
                    sources_payload = [
                        {
                            "document_name": s.document_name,
                            "page_number": s.page_number,
                            "excerpt": s.excerpt,
                            "score": s.score,
                        }
                        for s in ans.sources
                    ]
                    with st.expander("Sources", expanded=False):
                        for s in ans.sources:
                            if st.session_state.show_debug_scores:
                                st.markdown(
                                    f"**{s.document_name} · Page {s.page_number}**  ·  score `{s.score:.3f}`"
                                )
                            else:
                                st.markdown(f"**{s.document_name} · Page {s.page_number}**")
                            st.write(s.excerpt)
                            st.divider()

                    chat.append({"role": "assistant", "content": ans.text, "sources": sources_payload})


if __name__ == "__main__":
    main()

