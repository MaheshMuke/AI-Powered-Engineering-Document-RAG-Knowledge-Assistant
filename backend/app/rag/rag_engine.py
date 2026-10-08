"""
Automotive RAG (Retrieval-Augmented Generation) Engine.
Enforces project isolation, citation generation, prompt injection protection,
and evidence-based reasoning. Refuses to fabricate answers when evidence is lacking.
"""
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.rag.vector_store import vector_store
from backend.app.services.llm_provider import llm_service
from backend.app.security.security import sanitize_input_for_prompt_injection
from backend.app.models.models import AuditLog, Document

class AutomotiveRAGEngine:
    def __init__(self):
        self.min_similarity_threshold = 0.15

    def query(
        self,
        project_id: int,
        user_query: str,
        db: Session,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Executes an audited RAG query strictly against the target project's documents.
        """
        # Step 1: Input sanitization
        clean_query = sanitize_input_for_prompt_injection(user_query)

        # Step 2: Vector retrieval strictly scoped to project_id
        retrieved_chunks = vector_store.search(
            project_id=project_id,
            query=clean_query,
            top_k=top_k
        )

        # Step 3: Evidence Evaluation
        if not retrieved_chunks:
            # Check if any documents exist in project
            doc_count = db.query(Document).filter(Document.project_id == project_id).count()
            missing_info = (
                "No indexed engineering documents exist in this project."
                if doc_count == 0
                else "No matching technical specifications or requirements were found in the project vector database."
            )
            return {
                "answer": f"Insufficient approved project evidence to determine this.\n\nMissing context: {missing_info}",
                "confidence": 0.0,
                "citations": [],
                "limitations": "Zero relevant approved chunks retrieved. Autonomous inference prohibited without grounding documents.",
                "disclaimer": settings.AI_DISCLAIMER,
                "audit_id": None
            }

        # Step 4: Construct Citations & Metadata
        citations = []
        context_snippets = []
        for c in retrieved_chunks:
            meta = c.get("metadata", {})
            doc_name = meta.get("filename", "Unknown_Document.pdf")
            page_num = int(meta.get("page", 1))
            
            # Prioritize real section title over generic "Page X"
            sec_title = meta.get("section") or ""
            if not sec_title or sec_title.strip() == f"Page {page_num}":
                # Check first line of content for header pattern
                first_line = (c.get("content", "").splitlines() or [""])[0].strip()
                if first_line and not first_line.startswith("===") and len(first_line) < 70:
                    sec_title = first_line
                else:
                    sec_title = f"Page {page_num}"

            snip = c.get("content", "")[:350]
            retrieval_sim = float(c.get("similarity", 0.0))

            citations.append({
                "document_name": doc_name,
                "page": page_num,
                "section": sec_title,
                "chunk_id": c.get("chunk_id", ""),
                "snippet": snip,
                "confidence": retrieval_sim,  # Legacy backwards compatibility
                "retrieval_similarity": retrieval_sim
            })
            context_snippets.append(
                f"[DOCUMENT: {doc_name} | PAGE: {page_num} | SECTION: {sec_title}]\n{c.get('content', '')}"
            )

        # Step 5: System and Prompt Construction
        system_prompt = (
            "You are a specialized Automotive Systems Engineering AI Assistant.\n"
            "MANDATORY INSTRUCTIONS:\n"
            "1. DISTINGUISH SOURCE FACTS VS AI INFERENCES:\n"
            "   - Under '### Source-Supported Facts': Only quote or state direct specifications verbatim/directly from the provided documents. Cite document, page, and section.\n"
            "   - Under '### AI Engineering Observations' (optional): State technical interpretations, implications, or risks. Explicitly prefix with '[AI Engineering Observation]' and NEVER present inferences as document facts.\n"
            "2. STRICT HANDLING OF MISSING EVIDENCE:\n"
            "   - If the specific parameter, value, algorithm, CPU, clock, or metric requested is NOT explicitly stated in the approved documents, you MUST state:\n"
            "     'Insufficient approved project evidence to determine [item].'\n"
            "   - DO NOT fabricate, guess, infer, or hallucinate microcontrollers, clock speeds, CPU architectures, single-point fault metrics, ASIL metrics, or diagnostic formulas if not present in the text.\n"
            "3. NO COMPLIANCE CLAIMS: Never claim formal ISO 26262, ISO/SAE 21434, or ASPICE certification."
        )

        context_str = "\n\n---\n\n".join(context_snippets)
        full_prompt = (
            f"PROJECT ID: {project_id}\n\n"
            f"APPROVED PROJECT EVIDENCE:\n{context_str}\n\n"
            f"ENGINEERING QUERY: {clean_query}\n\n"
            "Formulate your response adhering strictly to the required structure:\n"
            "- If the document directly answers the query: state the exact value/facts under '### Source-Supported Facts' with citation (Document Name, Page, Section). Then provide any '### AI Engineering Observations' (if applicable).\n"
            "- If the document DOES NOT contain the requested information: state 'Insufficient approved project evidence to determine [item]' under '### Source-Supported Facts' and note what is missing."
        )

        # Step 6: Generate Answer
        raw_answer = llm_service.generate(full_prompt, system_prompt=system_prompt)

        # Step 7: Calculate Confidence & Limitations
        # Primary evidence retrieval similarity (highest scoring chunk)
        primary_sim = citations[0]["retrieval_similarity"] if citations else 0.0

        # Heuristic Evidence Confidence: Reflects whether evidence actually answers or contains query tokens
        # Check if the answer indicates insufficient evidence
        is_insufficient = "insufficient approved project evidence" in raw_answer.lower()
        if is_insufficient:
            overall_confidence = 0.0
            confidence_note = "Evidence Confidence: 0.0% (Requested parameter is not present in approved project documentation)."
        else:
            # Scale evidence confidence based on primary similarity and chunk density
            base_conf = min(0.95, primary_sim * 1.8 + 0.15)
            overall_confidence = round(base_conf, 2)
            confidence_note = (
                f"Overall Evidence Confidence: {int(overall_confidence * 100)}% | "
                f"Primary Evidence Retrieval Similarity: {primary_sim:.3f}. "
                "(Note: This score is an information retrieval grounding indicator, NOT a functional safety or compliance probability.)"
            )

        limitations = (
            "Results generated from retrieved project chunks. "
            "Evidence confidence is an information retrieval indicator and does not constitute safety compliance or engineering approval."
        )

        # Step 8: Create Audit Log
        audit = AuditLog(
            project_id=project_id,
            user_id=user_id,
            username=username,
            action="RAG_QUERY_EXECUTED",
            object_type="QUERY",
            object_id=clean_query[:64],
            old_value_json=None,
            new_value_json={
                "query": clean_query,
                "citations_count": len(citations),
                "primary_similarity": primary_sim,
                "evidence_confidence": overall_confidence
            },
            ai_model=llm_service.model,
            source_references=[c["chunk_id"] for c in citations]
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)

        return {
            "answer": raw_answer,
            "confidence": overall_confidence,
            "evidence_confidence": overall_confidence,
            "primary_similarity": primary_sim,
            "confidence_note": confidence_note,
            "citations": citations,
            "limitations": limitations,
            "disclaimer": settings.AI_DISCLAIMER,
            "audit_id": audit.id
        }

rag_engine = AutomotiveRAGEngine()
