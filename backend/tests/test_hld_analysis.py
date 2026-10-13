import csv
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.ingestion.chunker import chunk_document
from backend.app.ingestion.extractor import extract_document
from backend.app.ingestion.extractor import extract_text_from_pdf
from backend.app.main import app
from backend.app.models.models import (
    Document, DocumentChunk, DocumentVersion, Project, RoleEnum, User,
)
from backend.app.security.security import get_password_hash
from backend.app.services.hld_analysis import analyze_hld, compare_revisions, serialize_report
from backend.app.api import documents as documents_api


PROJECT_ROOT = Path(__file__).resolve().parents[2]
V1_PATH = PROJECT_ROOT / "data" / "sample_documents" / "ADAS_ECU_HLD_Specification_v1.txt"
V2_PATH = PROJECT_ROOT / "data" / "sample_documents" / "ADAS_ECU_HLD_Specification_v2.txt"


def _sample_chunks(path: Path, version: int, document_id: int = 10):
    pages = extract_document(str(path), "txt")
    chunks = chunk_document(
        project_id=1,
        document_id=document_id,
        document_version=version,
        filename=path.name,
        pages_data=pages,
        chunk_size=500,
    )
    return [{
        "document_id": chunk["document_id"],
        "version_number": chunk["document_version"],
        "filename": chunk["filename"],
        "page_number": chunk["page"],
        "section_title": chunk["section"],
        "chunk_id": chunk["chunk_id"],
        "content": chunk["content"],
    } for chunk in chunks]


def _one_chunk(text: str, version: int = 1, document_id: int = 10):
    return [{
        "document_id": document_id,
        "version_number": version,
        "filename": f"example-v{version}.txt",
        "page_number": 1,
        "section_title": "Component interfaces",
        "chunk_id": f"doc-{document_id}-v{version}-chunk-1",
        "content": text,
    }]


def test_component_inventory_extracts_documented_fields_and_citations():
    report = analyze_hld(_sample_chunks(V1_PATH, 1))
    camera = next(item for item in report["components"] if item["component_name"] == "SWC_CameraProcessing")
    assert camera["component_type"] == "SensorActuator"
    assert camera["execution_period"] == "33 ms"
    assert any("Acquires raw MIPI-CSI" in function for function in camera["functions"])
    assert camera["citations"][0]["document_name"] == V1_PATH.name
    assert camera["citations"][0]["page"] == 1
    assert camera["citations"][0]["chunk_id"]


def test_interface_matrix_has_explicit_source_target_and_communication_facts():
    report = analyze_hld(_sample_chunks(V1_PATH, 1))
    row = next(item for item in report["interface_matrix"] if item["interface_name"] == "IF_FusedTracks")
    assert row["source_component"] == "SWC_ObjectFusion"
    assert row["target_component"] == "SWC_TrajectoryPlanner"
    assert row["output_port"] == "P_FusedTrack"
    assert row["input_port"] == "R_FusedTrack"
    assert "CAN-FD" in row["protocol"]
    assert row["transmission_period"] == "50 ms"
    assert row["expected_period"] == "20 ms"
    assert row["data_type"] == "TargetTrajectory_t"
    assert row["input_data_type"] == "Insufficient evidence"


def test_dependencies_use_only_explicit_flow_evidence():
    report = analyze_hld(_sample_chunks(V1_PATH, 1))
    edges = {(item["source"], item["target"]) for item in report["dependencies"]["edges"]}
    assert ("SWC_ObjectFusion", "SWC_TrajectoryPlanner") in edges
    assert "digraph HLD" in report["dependencies"]["graphviz"]
    unrelated = analyze_hld(_one_chunk("SWC_A and SWC_B are listed in the same paragraph."))
    assert unrelated["dependencies"]["edges"] == []
    assert unrelated["dependencies"]["graphviz"].rstrip().endswith("}")
    cycle = analyze_hld(_one_chunk("SWC_A -> SWC_B\nSWC_B -> SWC_A"))
    finding = next(item for item in cycle["inconsistencies"] if item["category"] == "dependency")
    assert finding["classification"] == "inferred_concern"
    assert finding["citations"]


def test_mismatch_findings_include_evidence_severity_and_review_status():
    text = """1 SWC_Source
- Output Port: P_State (Interface: IF_State)
  * Protocol: CAN-FD
  * Data Type: uint16_t
  * Transmission periodicity is configured to 50 ms.
2 SWC_Target
- Input Port: R_State (Interface: IF_State)
  * Protocol: SOME/IP
  * Data Type: float_t
  * EXPECTATION: requires input data at 20 ms intervals.
"""
    report = analyze_hld(_one_chunk(text))
    categories = {item["category"] for item in report["inconsistencies"]}
    assert categories == {"signal_data_type", "timing", "interface"}
    for finding in report["inconsistencies"]:
        assert finding["classification"] == "explicit_contradiction"
        assert finding["severity"] == "HIGH"
        assert finding["severity_rationale"]
        assert finding["evidence"]
        assert finding["citations"][0]["chunk_id"] == "doc-10-v1-chunk-1"
        assert finding["engineering_review_status"] == "PENDING_ENGINEERING_REVIEW"


def test_revision_comparison_uses_real_revisions_and_both_revision_citations():
    before = _sample_chunks(V1_PATH, 1)
    after = _sample_chunks(V2_PATH, 2)
    comparison = compare_revisions(
        before,
        after,
        {"document_id": 10, "filename": V1_PATH.name, "version_number": 1},
        {"document_id": 10, "filename": V2_PATH.name, "version_number": 2},
    )
    changes = comparison["changes"]
    radar = next(item for item in changes if item["entity"] == "SWC_RadarFusionBridge")
    assert radar["change_type"] == "added"
    assert {cite["version"] for cite in radar["citations"]} == {1, 2}
    object_fusion = next(
        item for item in changes
        if item["category"] == "timing_requirements"
        and item["entity"] == "SWC_ObjectFusion|execution"
    )
    assert object_fusion["change_type"] == "modified"
    assert object_fusion["before"]["execution_period"] == "50 ms"
    assert object_fusion["after"]["execution_period"] == "20 ms"
    assert not any(item["entity"] == "SWC_BrakeActuatorDriver" and item["change_type"] == "removed" for item in changes)
    assert any(
        item["category"] == "signals"
        and item["entity"] == "RawUltrasonicDistance_t"
        and item["change_type"] == "removed"
        and item.get("explicit_removal_statement")
        for item in changes
    )
    for change in changes:
        assert {cite["version"] for cite in change["citations"]} == {1, 2}


def test_revision_comparison_detects_interface_signal_protocol_and_explicit_removals():
    before = _one_chunk("""1 SWC_Main
- Component Type: Application
- Output Port: P_Data (Interface: IF_Data)
  * Transmission period: 10 ms
- Output Port: P_Protocol (Interface: IF_Protocol)
  * Protocol: CAN-FD
- Output Port: P_Signal (Interface: IF_Signal)
  * Data Type: uint16_t
2 SWC_Retired
- Component Type: Application
""", 1, 22)
    after = _one_chunk("""1 SWC_Main
- Component Type: Application
- Output Port: P_Data_v2 (Interface: IF_Data)
  * Transmission period: 20 ms
- Output Port: P_Protocol (Interface: IF_Protocol)
  * Protocol: SOME/IP
- Output Port: P_Signal (Interface: IF_Signal)
  * Data Type: float_t
2 SWC_New [NEW COMPONENT]
- Component Type: Application
3 DEPRECATED ITEMS
- SWC_Retired removed from this architecture.
- Signal LegacySignal_t removed from the vehicle bus.
""", 2, 22)
    comparison = compare_revisions(
        before,
        after,
        {"document_id": 22, "filename": "revision.txt", "version_number": 1},
        {"document_id": 22, "filename": "revision.txt", "version_number": 2},
    )
    changes = comparison["changes"]
    assert any(item["category"] == "interfaces" and item["change_type"] == "modified" for item in changes)
    assert any(item["category"] == "signals" and item["change_type"] == "modified" for item in changes)
    assert any(item["category"] == "protocols" and item["change_type"] == "modified" for item in changes)
    assert any(item["category"] == "timing_requirements" and item["change_type"] == "modified" for item in changes)
    assert any(item["entity"] == "SWC_New" and item["change_type"] == "added" for item in changes)
    assert any(item["entity"] == "SWC_Retired" and item["change_type"] == "removed" for item in changes)
    assert any(item["entity"] == "LegacySignal_t" and item["change_type"] == "removed" for item in changes)
    assert all({cite["version"] for cite in item["citations"]} == {1, 2} for item in changes)


def test_unsupported_fields_are_labeled_and_never_fabricated():
    report = analyze_hld(_one_chunk("1 SWC_Minimal\n- Component Type: Application\n"))
    component = report["components"][0]
    assert component["component_type"] == "Application"
    assert component["execution_period"] == "Insufficient evidence"
    assert component["functions"] == ["Insufficient evidence"]
    assert component["ports"] == []
    input_only = analyze_hld(_one_chunk(
        "1 SWC_Target\n- Input Port: R_Unknown (Interface: IF_Unknown)\n"
    ))
    assert input_only["interface_matrix"][0]["source_component"] == "Insufficient evidence"
    assert input_only["interface_matrix"][0]["target_component"] == "SWC_Target"


def test_scanned_pdf_page_uses_ocr_fallback(tmp_path, monkeypatch):
    pdf_path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with pdf_path.open("wb") as output:
        writer.write(output)

    class RenderedPage:
        def render(self, scale):
            return self

        def to_pil(self):
            return "rendered-page"

    class FakePdfDocument:
        def __init__(self, path):
            assert path == str(pdf_path)

        def __getitem__(self, index):
            assert index == 0
            return RenderedPage()

    monkeypatch.setitem(
        sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=FakePdfDocument)
    )
    monkeypatch.setitem(
        sys.modules, "pytesseract",
        SimpleNamespace(image_to_string=lambda image: "OCR component text" if image == "rendered-page" else ""),
    )
    pages = extract_text_from_pdf(str(pdf_path))
    assert pages[0]["text"] == "OCR component text"


def test_structured_report_export_includes_citations_and_tables():
    payload = analyze_hld(_sample_chunks(V1_PATH, 1))
    json_bytes, json_type = serialize_report(payload, "json")
    assert json_type == "application/json"
    assert json.loads(json_bytes)["components"][0]["citations"]
    csv_bytes, csv_type = serialize_report(payload, "csv")
    assert csv_type.startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    assert {row["section"] for row in rows} >= {
        "component_inventory", "interface_matrix", "dependencies", "inconsistencies",
    }
    assert "citations" in rows[0]
    with pytest.raises(ValueError, match="Unsupported report format"):
        serialize_report(payload, "xml")


@pytest.fixture
def hld_api_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = test_session()
    user = User(
        username="hld-test-user",
        email="hld-test@example.invalid",
        hashed_password=get_password_hash("test-password"),
        role=RoleEnum.ENGINEER,
        is_active=True,
    )
    project = Project(name="HLD Test", key="HLD-TEST")
    db.add_all([user, project])
    db.flush()
    text = """1 SWC_Source
- Component Type: Application
- Execution Period: 50 ms
- Output Port: P_State (Interface: IF_State)
  * Data Type: uint16_t
  * Transmission periodicity is configured to 50 ms.
2 SWC_Target
- Component Type: Application
- Execution Period: 20 ms
- Input Port: R_State (Interface: IF_State)
  * Data Type: float_t
  * EXPECTATION: requires input data at 20 ms intervals.
"""
    for version_number, content in ((1, text), (2, text.replace("50 ms", "25 ms"))):
        document = db.query(Document).filter(Document.filename == "test-hld.txt").first()
        if document is None:
            document = Document(
                project_id=project.id, filename="test-hld.txt", file_type="txt",
                file_path="test-hld.txt", current_version=version_number,
                is_indexed=True, created_by_id=user.id,
            )
            db.add(document)
            db.flush()
        else:
            document.current_version = version_number
        db.add(DocumentVersion(
            document_id=document.id,
            version_number=version_number,
            file_path=f"test-hld-v{version_number}.txt",
            uploaded_by_id=user.id,
        ))
        db.add(DocumentChunk(
            project_id=project.id, document_id=document.id,
            version_number=version_number, chunk_id=f"hld-v{version_number}",
            page_number=1, section_title="Test", content=content, token_count=len(content.split()),
        ))
    db.commit()
    project_id = project.id
    document_id = document.id
    db.close()

    def override_get_db():
        session = test_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        token_response = client.post(
            "/api/v1/auth/login",
            json={"username": "hld-test-user", "password": "test-password"},
        )
        assert token_response.status_code == 200
        client.headers.update({
            "Authorization": f"Bearer {token_response.json()['access_token']}"
        })
        yield client, project_id, document_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_hld_api_persists_review_status_audit_and_export(hld_api_client):
    client, project_id, document_id = hld_api_client
    response = client.post(
        f"/api/v1/hld/{project_id}/analyze",
        json={"document_id": document_id, "version_number": 1},
    )
    assert response.status_code == 200, response.text
    analysis = response.json()
    finding = analysis["payload"]["inconsistencies"][0]
    reviewed = client.patch(
        f"/api/v1/hld/{project_id}/reports/{analysis['id']}/findings/{finding['finding_id']}",
        json={"reviewed": True, "review_note": "Checked against interface timing requirement."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["engineering_review_status"] == "REVIEWED"

    report = client.get(f"/api/v1/hld/{project_id}/reports/{analysis['id']}")
    assert report.status_code == 200
    saved_finding = report.json()["payload"]["inconsistencies"][0]
    assert saved_finding["engineering_review_status"] == "REVIEWED"
    assert saved_finding["review_note"] == "Checked against interface timing requirement."
    exported = client.get(
        f"/api/v1/hld/{project_id}/reports/{analysis['id']}/export?format=csv"
    )
    assert exported.status_code == 200
    assert "component_inventory" in exported.text
    assert "inconsistencies" in exported.text

    comparison = client.post(
        f"/api/v1/hld/{project_id}/compare",
        json={
            "before_document_id": document_id,
            "before_version_number": 1,
            "after_document_id": document_id,
            "after_version_number": 2,
        },
    )
    assert comparison.status_code == 200, comparison.text
    assert any(
        change["change_type"] == "modified"
        for change in comparison.json()["payload"]["changes"]
    )
    comparison_change = comparison.json()["payload"]["changes"][0]
    assert {cite["version"] for cite in comparison_change["citations"]} == {1, 2}
    audit_log = client.get(f"/api/v1/audit/{project_id}")
    assert audit_log.status_code == 200
    assert {
        row["action"] for row in audit_log.json()
    } >= {"HLD_ANALYSIS_GENERATED", "HLD_FINDING_REVIEW_STATUS_UPDATED", "HLD_REVISIONS_COMPARED"}


def test_same_name_uploads_keep_actual_document_versions(hld_api_client, tmp_path, monkeypatch):
    client, project_id, _ = hld_api_client
    monkeypatch.setattr(documents_api.settings, "UPLOAD_DIR", str(tmp_path))
    first = client.post(
        "/api/v1/documents/upload",
        data={"project_id": project_id},
        files={"file": ("hld-versions.txt", b"Revision one")},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/v1/documents/upload",
        data={"project_id": project_id},
        files={"file": ("hld-versions.txt", b"Revision two")},
    )
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["current_version"] == 2
    assert second.json()["is_indexed"] is False
    version_one = tmp_path / f"project_{project_id}" / f"document_{first.json()['id']}_v1_hld-versions.txt"
    version_two = tmp_path / f"project_{project_id}" / f"document_{first.json()['id']}_v2_hld-versions.txt"
    assert version_one.read_bytes() == b"Revision one"
    assert version_two.read_bytes() == b"Revision two"
    monkeypatch.setattr(documents_api.vector_store, "add_chunks", lambda **kwargs: None)
    indexed = client.post(
        f"/api/v1/documents/{first.json()['id']}/index"
        f"?version_number=1&project_id={project_id}"
    )
    assert indexed.status_code == 200, indexed.text
    assert indexed.json()["version_number"] == 1
    versions = client.get(
        f"/api/v1/documents/{first.json()['id']}/versions?project_id={project_id}"
    )
    assert versions.status_code == 200
    assert [item["is_indexed"] for item in versions.json()] == [True, False]
    documents = client.get(f"/api/v1/documents/?project_id={project_id}")
    assert documents.json()[-1]["is_indexed"] is False
