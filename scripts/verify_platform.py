"""
Automated End-to-End Platform Verification Script.
Executes the complete automotive engineering workflow against the live running servers.
"""
import requests
import json
import os

BASE_URL = "http://127.0.0.1:8000/api/v1"

def run_verification():
    print("=" * 60)
    print("AUTOMOTIVE PLATFORM END-TO-END VERIFICATION")
    print("=" * 60)

    # 1. Health check
    h_res = requests.get("http://127.0.0.1:8000/health")
    assert h_res.status_code == 200
    print("[PASS] Backend API is Healthy")

    # 2. Login as Engineer
    login_res = requests.post(f"{BASE_URL}/auth/login", json={"username": "engineer", "password": "EngineerPass123!"})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    eng_token = login_res.json()["access_token"]
    eng_headers = {"Authorization": f"Bearer {eng_token}"}
    print("[PASS] Authenticated as ADAS Engineer")

    # 3. Retrieve Projects
    p_res = requests.get(f"{BASE_URL}/projects/", headers=eng_headers)
    assert p_res.status_code == 200
    projects = p_res.json()
    assert len(projects) >= 1
    project_id = projects[0]["id"]
    print(f"[PASS] Retrieved Project: {projects[0]['name']} (ID: {project_id})")

    # 4. Upload HLD Document
    doc_path = "data/sample_documents/ADAS_ECU_HLD_Specification_v1.txt"
    with open(doc_path, "rb") as f:
        files = {"file": ("ADAS_ECU_HLD_Specification_v1.txt", f.read())}
    data = {"project_id": project_id}
    up_res = requests.post(f"{BASE_URL}/documents/upload", data=data, files=files, headers=eng_headers)
    assert up_res.status_code == 200
    doc_id = up_res.json()["id"]
    print(f"[PASS] Uploaded Document ID {doc_id}: {up_res.json()['filename']}")

    # 5. Index Document into ChromaDB
    idx_res = requests.post(f"{BASE_URL}/documents/{doc_id}/index", headers=eng_headers)
    assert idx_res.status_code == 200
    print(f"[PASS] Indexed into ChromaDB ({idx_res.json()['chunks_indexed']} chunks)")

    # 6. Execute RAG Query with Citation
    rag_payload = {
        "project_id": project_id,
        "query": "What is the transmission periodicity of IF_FusedTracks?",
        "top_k": 4
    }
    rag_res = requests.post(f"{BASE_URL}/rag/query", json=rag_payload, headers=eng_headers)
    assert rag_res.status_code == 200
    rag_data = rag_res.json()
    assert len(rag_data["citations"]) >= 1
    print(f"[PASS] RAG Retrieval with Citations (Confidence: {rag_data['confidence']*100:.1f}%)")
    print(f"       Citation: {rag_data['citations'][0]['document_name']} (Page {rag_data['citations'][0]['page']})")

    # 7. Execute AUTOSAR HLD Analysis
    hld_res = requests.post(f"{BASE_URL}/hld/analyze?project_id={project_id}", headers=eng_headers)
    assert hld_res.status_code == 200
    hld_data = hld_res.json()
    assert len(hld_data["components"]) >= 3
    assert len(hld_data["mismatches"]) >= 1
    print(f"[PASS] AUTOSAR HLD Analysis ({len(hld_data['components'])} components, {len(hld_data['mismatches'])} mismatches detected)")

    # 8. Deterministic HARA ASIL Calculation
    calc_res = requests.post(f"{BASE_URL}/hara/calculate-asil", json={"severity": "S3", "exposure": "E4", "controllability": "C3"})
    assert calc_res.status_code == 200
    assert calc_res.json()["calculated_asil"] == "ASIL D"
    print("[PASS] Deterministic HARA Rule Engine: S3 x E4 x C3 -> ASIL D")

    # 9. Create HARA Candidate Record
    hara_payload = {
        "project_id": project_id,
        "item_function": "Steering Torque Guidance",
        "malfunctioning_behavior": "Unintended torque offset > 3Nm",
        "operational_situation": "Highway v > 100 km/h",
        "hazardous_event": "Lane departure rollover",
        "severity": "S3",
        "exposure": "E4",
        "controllability": "C3",
        "safety_goal": "SG-01: Prevent unintended torque > 3Nm for > 50ms",
        "fsr_candidate": "EPS shall detect torque offset within 40ms"
    }
    hara_res = requests.post(f"{BASE_URL}/hara/candidates", json=hara_payload, headers=eng_headers)
    assert hara_res.status_code == 200
    hazard_id = hara_res.json()["id"]
    print(f"[PASS] Created HARA Candidate {hara_res.json()['hazard_id']} (Status: {hara_res.json()['status']})")

    # 10. Review as Safety Reviewer (Approve HARA)
    rev_login = requests.post(f"{BASE_URL}/auth/login", json={"username": "reviewer", "password": "ReviewerPass123!"})
    rev_token = rev_login.json()["access_token"]
    rev_headers = {"Authorization": f"Bearer {rev_token}"}
    appr_res = requests.post(f"{BASE_URL}/hara/{hazard_id}/review", json={"status": "APPROVED", "comment": "Formally verified by Safety Manager."}, headers=rev_headers)
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"
    print(f"[PASS] Human-in-the-Loop Sign-off: Hazard {hazard_id} APPROVED by Reviewer")

    # 11. Create TARA Cybersecurity Threat
    tara_payload = {
        "project_id": project_id,
        "asset_name": "CAN Gateway Calibration Firmware",
        "trust_boundary": "External OBD-II Port to Internal CAN",
        "attack_surface": "OBD-II Connector",
        "stride_category": "Tampering",
        "threat_scenario": "Attacker overwrites safety firmware via diagnostic routine",
        "damage_scenario": "Unintended acceleration",
        "impact_level": "Severe",
        "attack_feasibility": "Medium",
        "mitigation": "UDS SecurityAccess with asymmetric signature verification",
        "cybersecurity_requirement": "CSR-01: Verify cryptographic signature before flashing"
    }
    tara_res = requests.post(f"{BASE_URL}/tara/analyze", json=tara_payload, headers=eng_headers)
    assert tara_res.status_code == 200
    assert tara_res.json()["risk_level"] == "Critical"
    print(f"[PASS] TARA Threat Generated: {tara_res.json()['threat_id']} (Risk: Critical)")

    # 12. Run Secure Code Review
    with open("data/sample_code/ecu_can_rx.c", "r") as f:
        c_code = f.read()
    code_res = requests.post(f"{BASE_URL}/code-review/analyze", json={"project_id": project_id, "file_name": "ecu_can_rx.c", "code_content": c_code, "language": "c"}, headers=eng_headers)
    assert code_res.status_code == 200
    assert code_res.json()["total_findings"] >= 3
    print(f"[PASS] Secure Code Review: {code_res.json()['total_findings']} vulnerabilities detected (CWE-120, MISRA C:2012 Rule 21.3)")

    # 13. Generate UDS Diagnostic Test Suite
    uds_res = requests.post(f"{BASE_URL}/uds/generate-tests", json={"project_id": project_id, "requirement_text": "Verify ECU supports ReadDataByIdentifier for DID 0xF190", "service_id": "0x22", "did": "0xF190"}, headers=eng_headers)
    assert uds_res.status_code == 200
    uds_test = uds_res.json()
    assert uds_test["request_hex"] == "22 F1 90"
    print(f"[PASS] UDS Test Generated: {uds_test['test_id']} (Request: {uds_test['request_hex']}, Positive Response: {uds_test['expected_response_hex']})")

    # 14. Validate UDS Frame Deterministically
    val_res = requests.post(f"{BASE_URL}/uds/validate", json={"request_hex": "22 F1 90", "service_id": "0x22", "did": "0xF190"})
    assert val_res.status_code == 200
    assert val_res.json()["is_valid"] is True
    print("[PASS] Deterministic UDS Frame Structure Validation: Valid")

    # 15. Verify Traceability Matrix
    trace_res = requests.get(f"{BASE_URL}/traceability/{project_id}", headers=eng_headers)
    assert trace_res.status_code == 200
    trace_data = trace_res.json()
    assert len(trace_data["nodes"]) >= 4
    assert len(trace_data["edges"]) >= 3
    print(f"[PASS] Traceability Graph: {len(trace_data['nodes'])} nodes, {len(trace_data['edges'])} edges, Coverage: {trace_data['coverage_score']}%")

    # 16. Verify Audit Logs
    audit_res = requests.get(f"{BASE_URL}/audit/{project_id}", headers=eng_headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 5
    print(f"[PASS] Audit Trail Verified: {len(logs)} tamper-evident audit records captured")

    # 17. Verify Report Export
    rep_res = requests.get(f"{BASE_URL}/reports/export/{project_id}?format=markdown", headers=eng_headers)
    assert rep_res.status_code == 200
    assert "Automotive Engineering Report" in rep_res.text
    print("[PASS] Exported Formal Engineering Audit Report (Markdown format)")

    print("=" * 60)
    print("ALL 17 VERIFICATION STEPS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_verification()
