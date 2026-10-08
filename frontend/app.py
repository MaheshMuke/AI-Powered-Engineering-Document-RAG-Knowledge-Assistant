import streamlit as st
import pandas as pd
import json
import time
from frontend.components.ui import (
    apply_custom_css, render_safety_banner, render_status_badge
)
from frontend.utils.api_client import api_client

st.set_page_config(
    page_title="Engineering Document RAG Knowledge Assistant",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_custom_css()

# ==========================================
# SESSION STATE & AUTO-AUTHENTICATION
# ==========================================

ROLES = {
    "🏗️ Lead Architect (Admin)": ("admin", "AdminPass123!"),
    "⚙️ ADAS Engineer": ("engineer", "EngineerPass123!"),
    "🛡️ Reviewer": ("reviewer", "ReviewerPass123!"),
    "🔍 Auditor (Viewer)": ("viewer", "ViewerPass123!"),
}

if "current_project" not in st.session_state:
    st.session_state["current_project"] = None
if "active_role" not in st.session_state:
    st.session_state["active_role"] = list(ROLES.keys())[0]
if "token" not in st.session_state:
    st.session_state["token"] = None
if "user" not in st.session_state:
    st.session_state["user"] = None

def _auto_login(role_label: str):
    """Silently authenticate with the preset credentials for the given role."""
    username, password = ROLES[role_label]
    try:
        res = api_client.login(username, password)
        st.session_state["token"] = res["access_token"]
        st.session_state["user"] = res["user"]
    except Exception as e:
        st.error(f"Auto-login failed: {e}. Is the backend running?")
        st.stop()

# Auto-authenticate on first load or after role switch
if st.session_state["token"] is None:
    _auto_login(st.session_state["active_role"])

# ==========================================
# LOGGED IN SHELL & SIDEBAR
# ==========================================
user = st.session_state["user"]
token = st.session_state["token"]

# Load Projects
try:
    projects = api_client.get_projects(token)
except Exception:
    projects = []

if projects and not st.session_state["current_project"]:
    st.session_state["current_project"] = projects[0]

with st.sidebar:
    st.markdown("""
    <div style="padding-bottom: 12px; border-bottom: 1px solid var(--border);">
        <h3 style="color: var(--accent); margin: 0;">🔍 Engineering RAG</h3>
        <p style="color: var(--text-secondary); font-size: 12px; margin: 2px 0 0;">Knowledge Assistant</p>
    </div>
    """, unsafe_allow_html=True)

    # ---- Role Switcher ----
    st.markdown("### Active Role")
    role_labels = list(ROLES.keys())
    selected_role = st.selectbox(
        "Switch Role",
        role_labels,
        index=role_labels.index(st.session_state["active_role"]),
        key="role_selector",
        label_visibility="collapsed"
    )
    if selected_role != st.session_state["active_role"]:
        st.session_state["active_role"] = selected_role
        st.session_state["token"] = None  # force re-auth
        st.session_state["user"] = None
        st.rerun()

    st.markdown(
        f"<p style='color:var(--text-muted);font-size:12px;margin:4px 0 0;'>Role: <strong style='color:var(--text-secondary)'>{user['role']}</strong> &nbsp;|&nbsp; {user['username']}</p>",
        unsafe_allow_html=True
    )

    st.markdown("---")
    st.markdown("### Active Project")
    if projects:
        proj_names = [f"{p['key']} - {p['name']}" for p in projects]
        curr_idx = 0
        if st.session_state["current_project"]:
            for i, p in enumerate(projects):
                if p["id"] == st.session_state["current_project"]["id"]:
                    curr_idx = i
                    break
        sel_idx = st.selectbox("Select Project", range(len(projects)), format_func=lambda i: proj_names[i], index=curr_idx)
        st.session_state["current_project"] = projects[sel_idx]
    else:
        st.warning("No projects available.")

    with st.expander("+ Create New Project"):
        new_name = st.text_input("Project Name", key="new_proj_name")
        new_key = st.text_input("Project Key", key="new_proj_key", placeholder="e.g. BMS-01")
        new_desc = st.text_area("Description", key="new_proj_desc")
        if st.button("Create Project", use_container_width=True):
            if new_name and new_key:
                try:
                    p = api_client.create_project(token, new_name, new_key, new_desc)
                    st.success(f"Project '{new_name}' created!")
                    st.session_state["current_project"] = p
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.markdown("---")
    st.markdown("### Navigation")
    nav = st.radio(
        "Navigation",
        [
            "🔍 RAG Knowledge Assistant",
            "📁 Projects & Documents",
            "📊 Dashboard",
            "📜 Audit Logs"
        ],
        label_visibility="collapsed"
    )

current_proj = st.session_state["current_project"]
if not current_proj:
    st.info("Please create or select a project to proceed.")
    st.stop()

# HEADER
st.markdown(f"""
<div class="main-header">
    <div>
        <div class="brand-title">{nav}</div>
        <div class="brand-subtitle">Active Project: <strong>{current_proj['name']}</strong> ({current_proj['key']})</div>
    </div>
    <div style="text-align: right;">
        <span class="badge badge-ai">ENGINEERING KNOWLEDGE RAG</span>
    </div>
</div>
""", unsafe_allow_html=True)

render_safety_banner()

# ==========================================
# MODULE: RAG ASSISTANT (PRIMARY FOCUS)
# ==========================================
if nav == "🔍 RAG Knowledge Assistant":
    st.subheader("Engineering Document Q&A & Evidence Synthesis")
    st.write("Query indexed specifications with deterministic citation traceability, grounded evidence synthesis, and strict missing-information bounds.")

    # Show active documents in project
    try:
        docs = api_client.get_documents(token, current_proj["id"])
        indexed_docs = [d for d in docs if d["is_indexed"]]
        if indexed_docs:
            doc_tags = ", ".join([f"**{d['filename']}** (v{d['current_version']})" for d in indexed_docs])
            st.info(f"📚 **Indexed Knowledge Base ({len(indexed_docs)} documents):** {doc_tags}")
        else:
            st.warning("⚠️ No indexed documents in this project yet. Go to **'📁 Projects & Documents'** to upload and index an engineering specification.")
    except Exception:
        pass

    query_input = st.text_input(
        "Enter Engineering Question",
        value="What is the execution period of SWC_CameraProcessing?"
    )
    
    col_opt1, col_opt2 = st.columns([1, 3])
    with col_opt1:
        top_k = st.slider("Retrieval Depth (Chunks)", min_value=1, max_value=8, value=4)
    with col_opt2:
        st.caption("Prompt injection filtering, lexical+semantic vector search, and reranking are applied automatically.")

    if st.button("Ask Assistant", type="primary"):
        with st.spinner("Executing hybrid retrieval, reranking, and grounded evidence synthesis..."):
            try:
                res = api_client.query_rag(token, current_proj["id"], query_input, top_k=top_k)
                
                st.markdown("### Answer")
                st.markdown(res["answer"])
                
                conf_val = res.get("evidence_confidence", res.get("confidence", 0.0)) * 100
                prim_sim = res.get("primary_similarity", 0.0)
                conf_note = res.get("confidence_note", "")

                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.metric("Overall Evidence Confidence", f"{conf_val:.0f}%")
                with col_c2:
                    st.metric("Primary Retrieval Similarity", f"{prim_sim:.3f}")

                if conf_note:
                    st.info(conf_note)
                st.caption(f"**Audit Event ID:** `{res.get('audit_id')}` | **Limitations:** {res.get('limitations')}")

                st.markdown("### Source Citations & Evidence Snippets")
                if res.get("citations"):
                    for c in res["citations"]:
                        sim_disp = c.get("retrieval_similarity", c.get("confidence", 0.0))
                        st.markdown(f"""
                        <div class="citation-box">
                            <strong>SOURCE:</strong> {c['document_name']} | <strong>PAGE:</strong> {c['page']} | <strong>SECTION:</strong> {c['section']} | <strong>SIMILARITY:</strong> {sim_disp:.3f}<br>
                            <span style="color: var(--text-secondary); font-size: 13px;"><em>\"{c['snippet']}...\"</em></span>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.warning("No grounding citations were retrieved for this query.")
            except Exception as e:
                st.error(f"RAG query failed: {str(e)}")

# ==========================================
# MODULE: PROJECTS & DOCUMENTS
# ==========================================
elif nav == "📁 Projects & Documents":
    st.subheader("Document Ingestion & Knowledge Base Management")
    st.write("Upload engineering specifications (PDF, TXT, DOCX, C/H) to parse, chunk, embed, and store in project-isolated ChromaDB.")

    doc_col1, doc_col2 = st.columns([1, 1])

    with doc_col1:
        st.markdown("#### Upload Specification")
        uploaded_file = st.file_uploader(
            "Choose specification file",
            type=["pdf", "docx", "txt", "c", "h", "json"]
        )

        if uploaded_file is not None:
            if st.button("Upload & Prepare", type="primary"):
                try:
                    res = api_client.upload_document(token, current_proj["id"], uploaded_file.name, uploaded_file.getvalue())
                    st.success(f"File uploaded successfully: {res['filename']}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with doc_col2:
        st.markdown("#### Project Documents")
        try:
            docs = api_client.get_documents(token, current_proj["id"])
            if docs:
                for d in docs:
                    with st.container():
                        st.markdown(f"""
                        <div style="background-color: var(--bg-surface-2); padding: 12px 16px; border-radius: 6px; margin-bottom: 8px; border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <strong style="font-size: 15px; color: var(--text-primary);">📄 {d['filename']}</strong>
                                <div style="font-size: 12px; color: var(--text-secondary);">Type: {d['file_type'].upper()} | Version: v{d['current_version']} | Total Pages: {d['total_pages']}</div>
                            </div>
                            <div>
                                {'<span class="badge badge-approved">INDEXED</span>' if d['is_indexed'] else '<span class="badge badge-review">PENDING INDEX</span>'}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        if not d['is_indexed']:
                            if st.button(f"Index {d['filename']}", key=f"idx_{d['id']}", type="primary"):
                                with st.spinner("Extracting text, chunking, and embedding into ChromaDB..."):
                                    idx_res = api_client.index_document(token, d['id'])
                                    st.success(f"Indexed {idx_res['chunks_indexed']} chunks across {idx_res['total_pages']} pages into ChromaDB!")
                                    st.rerun()
            else:
                st.info("No documents uploaded yet. Upload a specification to begin.")
        except Exception as e:
            st.error(str(e))

# ==========================================
# MODULE: DASHBOARD
# ==========================================
elif nav == "📊 Dashboard":
    st.subheader("Knowledge Base Analytics & RAG Activity")
    try:
        docs = api_client.get_documents(token, current_proj["id"])
        audits = api_client.get_audit_logs(token, current_proj["id"])
    except Exception as e:
        docs, audits = [], []

    indexed_count = sum(1 for d in docs if d["is_indexed"])
    query_count = sum(1 for a in audits if a.get("action") == "RAG_QUERY")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(docs)}</div>
            <div class="metric-label">Total Documents</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{indexed_count}</div>
            <div class="metric-label">Indexed In ChromaDB</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{query_count}</div>
            <div class="metric-label">RAG Queries Processed</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### System Configuration")
    cfg_col1, cfg_col2 = st.columns(2)
    with cfg_col1:
        st.markdown("""
        - **Retrieval Engine:** Lexical-Semantic Hybrid with Exact-Token Booster
        - **Vector Database:** Project-Isolated ChromaDB
        - **Reranking:** Section & Component Entity-Aware Weighting
        """)
    with cfg_col2:
        st.markdown("""
        - **Synthesis Bounds:** Source Facts vs AI Engineering Observations
        - **Hallucination Control:** Strict Missing-Evidence Fallback
        - **Security:** Anti-Prompt Injection Sanitization & Project-Scoped Multi-Tenancy
        """)

# ==========================================
# MODULE: AUDIT LOGS
# ==========================================
elif nav == "📜 Audit Logs":
    st.subheader("Engineering Audit Trail & Compliance Log")
    st.write("Tamper-evident log of every document upload, indexing event, and RAG knowledge query.")

    try:
        logs = api_client.get_audit_logs(token, current_proj["id"])
        if logs:
            df_logs = pd.DataFrame([
                {
                    "Timestamp": l["created_at"],
                    "Action": l["action"],
                    "User": l["username"],
                    "Object Type": l["object_type"],
                    "Object ID": l["object_id"],
                    "AI Model": l.get("ai_model")
                }
                for l in logs
            ])
            st.dataframe(df_logs, use_container_width=True)
        else:
            st.info("No audit logs recorded for this project yet.")
    except Exception as e:
        st.error(str(e))
