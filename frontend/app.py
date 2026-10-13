import streamlit as st
import pandas as pd
import json
import time
from html import escape
from frontend.components.ui import (
    apply_custom_css, render_safety_banner, render_status_badge
)
from frontend.utils.api_client import api_client


def _render_dependency_graph(nodes, edges):
    """Render the extracted directed flow without a system Graphviz dependency."""
    ordered_nodes = list(nodes)
    if not ordered_nodes:
        st.info("Insufficient evidence: the source does not document component nodes.")
        return
    width = 660
    row_height = 86
    height = max(120, 48 + row_height * len(ordered_nodes))
    y_positions = {node: 34 + row_height * index for index, node in enumerate(ordered_nodes)}
    svg_edges = []
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        if source not in y_positions or target not in y_positions:
            continue
        source_y = y_positions[source] + 22
        target_y = y_positions[target] - 22
        svg_edges.append(
            f'<path d="M 330 {source_y} L 330 {target_y}" '
            'stroke="#6b8499" stroke-width="2" fill="none" marker-end="url(#arrow)"/>'
        )
        if edge["interface_name"] != "Insufficient evidence":
            svg_edges.append(
                f'<text x="342" y="{(source_y + target_y) / 2}" '
                'fill="#afc2d2" font-size="12">'
                f'{escape(edge["interface_name"])}</text>'
            )
    svg_nodes = []
    for node in ordered_nodes:
        y = y_positions[node]
        svg_nodes.append(
            f'<rect x="170" y="{y - 21}" width="320" height="44" rx="8" '
            'fill="#1f3446" stroke="#54748e"/>'
            f'<text x="330" y="{y + 5}" text-anchor="middle" '
            'fill="#f2f6fa" font-size="14">'
            f'{escape(node)}</text>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Documented HLD dependencies">'
        '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="6" refY="3" '
        'orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#6b8499"/></marker></defs>'
        + "".join(svg_edges) + "".join(svg_nodes) + "</svg>"
    )
    st.components.v1.html(svg, height=height, scrolling=False)

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
            "Dashboard",
            "Projects & Documents",
            "RAG Knowledge Assistant",
            "HLD Analysis",
            "Revision Comparison",
            "Findings & Reports",
            "Audit Logs",
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
if nav == "RAG Knowledge Assistant":
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
            st.warning("⚠️ No indexed documents in this project yet. Go to **Projects & Documents** to upload and index an engineering specification.")
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
elif nav == "Projects & Documents":
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
                                    idx_res = api_client.index_document(
                                        token, d['id'], project_id=current_proj["id"]
                                    )
                                    st.success(f"Indexed revision v{idx_res['version_number']}: {idx_res['chunks_indexed']} chunks across {idx_res['total_pages']} pages into ChromaDB!")
                                    st.rerun()
            else:
                st.info("No documents uploaded yet. Upload a specification to begin.")
        except Exception as e:
            st.error(str(e))

# ==========================================
# MODULE: DASHBOARD
# ==========================================
elif nav == "Dashboard":
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
elif nav == "HLD Analysis":
    st.subheader("AUTOSAR HLD Component and Interface Analysis")
    st.write("Extracts only documented architecture facts from indexed project revisions. All results are advisory and require engineering review.")
    docs = api_client.get_documents(token, current_proj["id"])
    if not docs:
        st.info("Upload an HLD in Projects & Documents before analysis.")
    else:
        selected_doc = st.selectbox(
            "HLD document",
            docs,
            format_func=lambda item: item["filename"],
            key="hld_analysis_document",
        )
        versions = api_client.get_document_versions(
            token, current_proj["id"], selected_doc["id"]
        )
        selected_version = None
        if not versions:
            st.warning("This document has no stored revision metadata. Re-upload the document to enable revision analysis.")
        else:
            version_numbers = [item["version_number"] for item in versions]
            selected_version = st.selectbox(
                "Revision",
                version_numbers,
                index=version_numbers.index(selected_doc["current_version"])
                if selected_doc["current_version"] in version_numbers else len(version_numbers) - 1,
                format_func=lambda version: (
                    f"v{version} ({'indexed' if next(v for v in versions if v['version_number'] == version)['is_indexed'] else 'not indexed'})"
                ),
                key="hld_analysis_version",
            )
            selected_revision = next(
                item for item in versions if item["version_number"] == selected_version
            )
            if not selected_revision["is_indexed"]:
                st.warning("Index this exact revision before HLD analysis.")
                if st.button("Index selected revision", key="index_analysis_revision"):
                    try:
                        api_client.index_document(
                            token, selected_doc["id"], selected_version,
                            project_id=current_proj["id"],
                        )
                        st.success(f"Indexed revision v{selected_version}.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Revision indexing failed: {exc}")
            if st.button(
                "Analyze HLD", type="primary",
                disabled=not selected_revision["is_indexed"],
            ):
                with st.spinner("Extracting documented components, interfaces, flows, and potential inconsistencies..."):
                    try:
                        result = api_client.analyze_hld(
                            token, current_proj["id"], selected_doc["id"], selected_version
                        )
                        st.session_state["active_hld_report_id"] = result["id"]
                        st.session_state["active_hld_report"] = result["payload"]
                        st.session_state["active_hld_report_type"] = "analysis"
                        st.session_state["active_hld_report_project_id"] = current_proj["id"]
                        st.success("Evidence-grounded analysis report saved.")
                    except Exception as exc:
                        st.error(f"HLD analysis failed: {exc}")
        payload = st.session_state.get("active_hld_report")
        if (
            st.session_state.get("active_hld_report_type") != "analysis"
            or st.session_state.get("active_hld_report_project_id") != current_proj["id"]
            or not payload
            or selected_version is None
            or payload.get("source_revision", {}).get("document_id") != selected_doc["id"]
            or payload.get("source_revision", {}).get("version_number") != selected_version
        ):
            payload = None
        if payload:
            st.markdown("#### Component Inventory")
            st.dataframe(pd.DataFrame([{
                "Component": item["component_name"],
                "Type": item["component_type"],
                "Functions": "; ".join(item["functions"]),
                "Execution Period": item["execution_period"],
                "Source Citations": "; ".join(
                    f"{cite['document_name']} v{cite['version']} p.{cite['page']}"
                    for cite in item["citations"]
                ),
            } for item in payload["components"]]), use_container_width=True)
            st.markdown("#### Ports")
            port_rows = [
                {key: value for key, value in port.items() if key != "citations"}
                for component in payload["components"] for port in component["ports"]
            ]
            if port_rows:
                st.dataframe(pd.DataFrame(port_rows), use_container_width=True)
            else:
                st.info("Insufficient evidence: no input/output ports were extracted.")
            st.markdown("#### Interface and Communication Matrix")
            st.dataframe(pd.DataFrame([{
                key: value for key, value in row.items() if key != "citations"
            } for row in payload["interface_matrix"]]), use_container_width=True)
            st.markdown("#### Documented Dependencies")
            edges = payload["dependencies"]["edges"]
            if edges:
                _render_dependency_graph(payload["dependencies"]["nodes"], edges)
                st.dataframe(pd.DataFrame([{
                    "Source": edge["source"], "Target": edge["target"],
                    "Interface": edge["interface_name"],
                    "Evidence": edge["evidence_type"],
                } for edge in edges]), use_container_width=True)
            else:
                st.info("Insufficient evidence: no dependency connections were explicitly documented.")
            st.markdown("#### Potential Inconsistencies")
            st.dataframe(pd.DataFrame([{
                "Severity": finding["severity"],
                "Classification": finding["classification"],
                "Finding": finding["title"],
                "Evidence": finding["evidence"],
                "Severity Rationale": finding["severity_rationale"],
                "Review Status": finding["engineering_review_status"],
                "Citations": "; ".join(
                    f"{cite['document_name']} v{cite['version']} p.{cite['page']}"
                    for cite in finding["citations"]
                ),
            } for finding in payload["inconsistencies"]]), use_container_width=True)
            st.caption(payload["disclaimer"])

elif nav == "Revision Comparison":
    st.subheader("Compare Actual Indexed HLD Revisions")
    st.write("Choose two uploaded document revisions. Any revision not yet indexed can be indexed directly here; changes are never generated without source content.")
    docs = api_client.get_documents(token, current_proj["id"])
    if not docs:
        st.info("Upload HLD revisions in Projects & Documents before comparison.")
    else:
        before_doc = st.selectbox(
            "Earlier revision document", docs,
            format_func=lambda item: item["filename"], key="before_hld_doc",
        )
        after_doc = st.selectbox(
            "Later revision document", docs,
            format_func=lambda item: item["filename"], key="after_hld_doc",
        )
        before_versions = api_client.get_document_versions(
            token, current_proj["id"], before_doc["id"]
        )
        after_versions = api_client.get_document_versions(
            token, current_proj["id"], after_doc["id"]
        )
        if not before_versions or not after_versions:
            st.warning("One or both documents have no stored revision metadata.")
        else:
            before_numbers = [item["version_number"] for item in before_versions]
            after_numbers = [item["version_number"] for item in after_versions]
            before_version = st.selectbox(
                "Earlier revision", before_numbers,
                format_func=lambda version: (
                    f"v{version} ({'indexed' if next(v for v in before_versions if v['version_number'] == version)['is_indexed'] else 'not indexed'})"
                ),
                key="before_hld_version",
            )
            after_version = st.selectbox(
                "Later revision", after_numbers,
                format_func=lambda version: (
                    f"v{version} ({'indexed' if next(v for v in after_versions if v['version_number'] == version)['is_indexed'] else 'not indexed'})"
                ),
                key="after_hld_version",
            )
            before_ready = next(v for v in before_versions if v["version_number"] == before_version)["is_indexed"]
            after_ready = next(v for v in after_versions if v["version_number"] == after_version)["is_indexed"]
            if not before_ready and st.button("Index earlier revision", key="index_before_revision"):
                try:
                    api_client.index_document(
                        token, before_doc["id"], before_version,
                        project_id=current_proj["id"],
                    )
                    st.success(f"Indexed earlier revision v{before_version}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Revision indexing failed: {exc}")
            if not after_ready and st.button("Index later revision", key="index_after_revision"):
                try:
                    api_client.index_document(
                        token, after_doc["id"], after_version,
                        project_id=current_proj["id"],
                    )
                    st.success(f"Indexed later revision v{after_version}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Revision indexing failed: {exc}")
            if st.button(
                "Compare Revisions", type="primary",
                disabled=not (before_ready and after_ready),
            ):
                try:
                    result = api_client.compare_hld_revisions(
                        token, current_proj["id"], before_doc["id"], before_version,
                        after_doc["id"], after_version,
                    )
                    st.session_state["active_hld_report_id"] = result["id"]
                    st.session_state["active_hld_report"] = result["payload"]
                    st.session_state["active_hld_report_type"] = "revision_comparison"
                    st.session_state["active_hld_report_project_id"] = current_proj["id"]
                    st.success(f"Comparison saved with {len(result['payload']['changes'])} documented changes.")
                except Exception as exc:
                    st.error(f"Revision comparison failed: {exc}")
            payload = st.session_state.get("active_hld_report")
            if (
                payload
                and st.session_state.get("active_hld_report_type") == "revision_comparison"
                and st.session_state.get("active_hld_report_project_id") == current_proj["id"]
                and payload.get("before_revision", {}).get("document_id") == before_doc["id"]
                and payload.get("before_revision", {}).get("version_number") == before_version
                and payload.get("after_revision", {}).get("document_id") == after_doc["id"]
                and payload.get("after_revision", {}).get("version_number") == after_version
            ):
                st.dataframe(pd.DataFrame([{
                "Category": change["category"],
                "Change": change["change_type"],
                "Entity": change["entity"],
                "Before": json.dumps(change["before"], ensure_ascii=False),
                "After": json.dumps(change["after"], ensure_ascii=False),
                "Citations": "; ".join(
                    f"{cite['document_name']} v{cite['version']} p.{cite['page']}"
                    for cite in change["citations"]
                ),
                "Review Status": change["engineering_review_status"],
                } for change in payload["changes"]]), use_container_width=True)
                st.caption(payload["disclaimer"])

elif nav == "Findings & Reports":
    st.subheader("HLD Findings and Structured Reports")
    reports = api_client.get_hld_reports(token, current_proj["id"])
    if not reports:
        st.info("Run an HLD analysis or revision comparison to create a report.")
    else:
        chosen_report = st.selectbox(
            "Saved report", reports,
            format_func=lambda item: f"#{item['id']} {item['title']}",
            key="saved_hld_report",
        )
        report = api_client.get_hld_report(token, current_proj["id"], chosen_report["id"])
        payload = report["payload"]
        findings = payload.get("inconsistencies", [])
        changes = payload.get("changes", [])
        if findings:
            st.markdown("#### Inconsistency Findings")
            st.dataframe(pd.DataFrame([{
                "Severity": item["severity"], "Type": item["classification"],
                "Finding": item["title"], "Evidence": item["evidence"],
                "Rationale": item["severity_rationale"],
                "Review Status": item["engineering_review_status"],
                "Citations": "; ".join(
                    f"{cite['document_name']} v{cite['version']} p.{cite['page']}"
                    for cite in item["citations"]
                ),
            } for item in findings]), use_container_width=True)
        if changes:
            st.markdown("#### Revision Changes")
            st.dataframe(pd.DataFrame([{
                "Category": item["category"], "Change": item["change_type"],
                "Entity": item["entity"],
                "Before": json.dumps(item["before"], ensure_ascii=False),
                "After": json.dumps(item["after"], ensure_ascii=False),
                "Review Status": item["engineering_review_status"],
                "Citations": "; ".join(
                    f"{cite['document_name']} v{cite['version']} p.{cite['page']}"
                    for cite in item["citations"]
                ),
            } for item in changes]), use_container_width=True)
        reviewable = [
            item for item in findings + changes
            if item["engineering_review_status"] != "REVIEWED"
        ]
        if reviewable:
            selected_item = st.selectbox(
                "Finding or change to mark reviewed", reviewable,
                format_func=lambda item: item.get("title", item["entity"]),
                key="finding_to_review",
            )
            review_note = st.text_input("Engineering review note (optional)")
            if st.button("Mark as reviewed"):
                item_id = selected_item.get("finding_id", selected_item.get("change_id"))
                try:
                    api_client.review_hld_finding(
                        token, current_proj["id"], report["id"], item_id, review_note
                    )
                    st.success("Review status recorded; this does not constitute architecture approval.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not update review status: {exc}")
        st.markdown("#### Export")
        export_col1, export_col2 = st.columns(2)
        for column, output_format in ((export_col1, "json"), (export_col2, "csv")):
            try:
                report_bytes = api_client.export_hld_report(
                    token, current_proj["id"], report["id"], output_format
                )
                column.download_button(
                    f"Download {output_format.upper()}",
                    report_bytes,
                    file_name=f"hld-report-{report['id']}.{output_format}",
                    mime="application/json" if output_format == "json" else "text/csv",
                )
            except Exception as exc:
                st.error(f"Report export failed: {exc}")
        st.caption(payload.get("disclaimer", "Advisory results; engineering review is required."))

elif nav == "Audit Logs":
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
