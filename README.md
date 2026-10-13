# Engineering Document RAG Knowledge Assistant

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-red.svg)](https://streamlit.io/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-VectorStore-purple.svg)](https://www.trychroma.com/)

An AI-powered **Engineering Document RAG Knowledge Assistant** built for systems, automotive, and software engineering specifications. It enables reliable question answering grounded strictly in uploaded project documentation with deterministic section citations, separate source facts vs AI inferences, and strict guardrails against hallucination and prompt injection.

---

## 1. System Architecture

```
                  ENGINEERING USER / UI
                            │
                            ▼
              STREAMLIT INTERFACE (Port 8501)
                            │
                            ▼
               FASTAPI BACKEND (Port 8000)
                            │
       ┌────────────────────┼────────────────────┐
       ▼                                     ▼
     Project &         P            Audit Trail
  Document Management       (Tamper-Evident)
       │                    │                    │
       └─────────┼────────────────────┘
                            │
                            ▼
               ENGINEERING RAG PIPELINE
                            │
  ┌─────────────────────────┼─────────────────────────┐
  ▼                         ▼                         ▼
Lexical + Semantic     ChromaDB Vector Store     LLM Synthesis
  Hybrid Retrieval      (Project-Isolated)     (Facts vs Inferences)
  + Boost & Rerank                               + Citations
```

---

## 2. Core Capabilities

### 📄 Context-Aware Ingestion & Chunking
- Parses PDF, TXT, DOCX, and source header specifications.
- Detects engineering hierarchy (e.g. `2.1 SWC_CameraProcessing`, `4. SAFETY ALLOCATIONS`) to preserve precise section metadata in citations.
- Overlapping recursive character chunking preserves critical technical parameters (execution periods, buffer sizes, pinouts).

### 🔍 Hybrid Lexical & Semantic Retrieval with Entity Reranking
- Combines semantic vector similarity with token-level lexical matching.
- Entity-aware boosting prioritizes exact component identifiers (`SWC_CameraProcessing`, `IF_FusedTracks`) and engineering metrics (`33 ms`, `ASIL D`).
- Multi-tenant ChromaDB stores embeddings partitioned strictly by `project_id`.

### 🛡️ Grounded Evidence Synthesis & Guardrails
- **Facts vs AI Observations:** Distinguishes verified facts from AI engineering inferences.
- **Strict Fallback:** If requested specifications do not contain supporting evidence, responds with `"Insufficient approved project evidence to determine..."`.
- **Confidence Metrics:** Exposes both vector retrieval similarity and evidence confidence.
- **Prompt Injection Defense:** Filters common jailbreaks and instruction-override patterns prior to vector query execution.
- **Audit Logging:** Every query, retrieved chunk, and model response is permanently recorded in the database.

### 🧩 AUTOSAR HLD Analysis
- Extracts component inventories, ports, interfaces, data types, protocols, execution/transmission periods, and explicit dependency flows from indexed document revisions.
- Flags potential interface, timing, and data-type conflicts with supporting citations, severity rationale, and an engineering-review status.
- Compares two selected, indexed document revisions and exports analysis/comparison reports as JSON or CSV.
- Analysis is advisory and does not approve architectures or establish ISO compliance or safety certification. Missing source detail is labeled as insufficient evidence.
- Scanned PDF pages use OCR when needed. OCR requires the Python dependencies in `backend/requirements.txt` and the Tesseract OCR application installed and available on `PATH`.

---

## 3. Quick Start & Execution

### 1. Environment Setup
```bash
# Clone the repository and navigate to root
cd tata_project

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate # Linux/macOS

# Install dependencies
pip install -r backend/requirements.txt
pip install streamlit
```

### 2. Configure Environment (`.env`)
```ini
LLM_PROVIDER=openai
LLM_API_KEY=your_openrouter_or_openai_key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=inclusionai/ling-3.0-flash-sante:free
CHROMA_PERSIST_DIRECTORY=./chroma_data
```

### 3. Run Backend & Frontend
```bash
# Terminal 1: FastAPI Backend
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2: Streamlit UI
streamlit run frontend/app.py --server.port 8501
```

Access the UI at `http://localhost:8501`.

---

## 4. Default Credentials

| Role | Username | Password |
|---|---|---|
| Lead Architect (Admin) | `admin` | `AdminPass123!` |
| ADAS Engineer | `engineer` | `EngineerPass123!` |
| Technical Reviewer | `reviewer` | `ReviewerPass123!` |
| Engineering Auditor | `viewer` | `ViewerPass123!` |

---

## 5. Automated Test Suite

Run the full pytest suite:
```bash
pytest backend/tests/ -v
```

Tests cover:
- Authentication, tokens, and role permissions
- Multi-tenant project data isolation
- Document upload, text parsing, and ChromaDB vector indexing
- Hybrid RAG retrieval, citations, and confidence scoring
- Prompt injection protection and negative missing-evidence behavior
- HLD extraction, explicit dependency mapping, mismatch detection, revision comparison, citations, missing evidence, and structured report export
