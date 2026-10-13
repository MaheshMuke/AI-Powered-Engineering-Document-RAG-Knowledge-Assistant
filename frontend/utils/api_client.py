import os
import requests
from typing import Dict, Any, Optional, List

API_BASE_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000/api/v1")

class APIClient:
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def _headers(self, token: Optional[str] = None) -> Dict[str, str]:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def login(self, username: str, password: str) -> Dict[str, Any]:
        url = f"{self.base_url}/auth/login"
        resp = requests.post(url, json={"username": username, "password": password}, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_projects(self, token: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/projects/"
        resp = requests.get(url, headers=self._headers(token), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def create_project(self, token: str, name: str, key: str, description: str = "") -> Dict[str, Any]:
        url = f"{self.base_url}/projects/"
        resp = requests.post(url, json={"name": name, "key": key, "description": description}, headers=self._headers(token), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_documents(self, token: str, project_id: int) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/documents/?project_id={project_id}"
        resp = requests.get(url, headers=self._headers(token), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_document_versions(
        self, token: str, project_id: int, document_id: int
    ) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/documents/{document_id}/versions"
        resp = requests.get(
            url, params={"project_id": project_id},
            headers=self._headers(token), timeout=15
        )
        resp.raise_for_status()
        return resp.json()

    def upload_document(self, token: str, project_id: int, file_name: str, file_bytes: bytes) -> Dict[str, Any]:
        url = f"{self.base_url}/documents/upload"
        files = {"file": (file_name, file_bytes)}
        data = {"project_id": project_id}
        resp = requests.post(url, data=data, files=files, headers=self._headers(token), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def index_document(
        self,
        token: str,
        document_id: int,
        version_number: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/documents/{document_id}/index"
        params = {
            key: value for key, value in {
                "version_number": version_number, "project_id": project_id
            }.items() if value is not None
        }
        resp = requests.post(url, params=params, headers=self._headers(token), timeout=60)
        resp.raise_for_status()
        return resp.json()

    def query_rag(self, token: str, project_id: int, query: str, top_k: int = 5) -> Dict[str, Any]:
        url = f"{self.base_url}/rag/query"
        payload = {"project_id": project_id, "query": query, "top_k": top_k}
        resp = requests.post(url, json=payload, headers=self._headers(token), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_audit_logs(self, token: str, project_id: int) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/audit/{project_id}"
        resp = requests.get(url, headers=self._headers(token), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def analyze_hld(
        self, token: str, project_id: int, document_id: int, version_number: Optional[int] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/hld/{project_id}/analyze"
        payload = {"document_id": document_id, "version_number": version_number}
        resp = requests.post(url, json=payload, headers=self._headers(token), timeout=60)
        resp.raise_for_status()
        return resp.json()

    def compare_hld_revisions(
        self,
        token: str,
        project_id: int,
        before_document_id: int,
        before_version_number: int,
        after_document_id: int,
        after_version_number: int,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/hld/{project_id}/compare"
        payload = {
            "before_document_id": before_document_id,
            "before_version_number": before_version_number,
            "after_document_id": after_document_id,
            "after_version_number": after_version_number,
        }
        resp = requests.post(url, json=payload, headers=self._headers(token), timeout=60)
        resp.raise_for_status()
        return resp.json()

    def get_hld_reports(self, token: str, project_id: int) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/hld/{project_id}/reports"
        resp = requests.get(url, headers=self._headers(token), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_hld_report(self, token: str, project_id: int, report_id: int) -> Dict[str, Any]:
        url = f"{self.base_url}/hld/{project_id}/reports/{report_id}"
        resp = requests.get(url, headers=self._headers(token), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def review_hld_finding(
        self, token: str, project_id: int, report_id: int, finding_id: str, review_note: str = ""
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/hld/{project_id}/reports/{report_id}/findings/{finding_id}"
        resp = requests.patch(
            url,
            json={"reviewed": True, "review_note": review_note or None},
            headers=self._headers(token),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def export_hld_report(self, token: str, project_id: int, report_id: int, output_format: str) -> bytes:
        url = f"{self.base_url}/hld/{project_id}/reports/{report_id}/export"
        resp = requests.get(
            url,
            params={"format": output_format},
            headers=self._headers(token),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.content

api_client = APIClient()
