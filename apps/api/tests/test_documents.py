import io
import zipfile

from fastapi.testclient import TestClient
from test_auth import register


def create_project(client: TestClient, token: str) -> str:
    response = client.post(
        "/api/v1/projects",
        json={"name": "Knowledge"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_text_document_lifecycle_and_owner_isolation(client: TestClient) -> None:
    owner = register(client, "docs-owner@example.com")
    other = register(client, "docs-other@example.com")
    project_id = create_project(client, owner["access_token"])
    headers = {"Authorization": f"Bearer {owner['access_token']}"}

    uploaded = client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("notes.md", b"# Safe knowledge\nUseful facts", "text/markdown")},
    )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["status"] == "ready"
    assert body["original_filename"] == "notes.md"
    assert len(body["sha256"]) == 64

    listed = client.get(f"/api/v1/projects/{project_id}/documents", headers=headers)
    assert [item["id"] for item in listed.json()] == [body["id"]]
    denied = client.get(
        f"/api/v1/projects/{project_id}/documents",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert denied.status_code == 404
    deleted = client.delete(
        f"/api/v1/projects/{project_id}/documents/{body['id']}", headers=headers
    )
    assert deleted.status_code == 204


def test_spoofed_pdf_and_binary_text_are_rejected(client: TestClient) -> None:
    session = register(client, "invalid-files@example.com")
    project_id = create_project(client, session["access_token"])
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    fake_pdf = client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("malware.pdf", b"not a pdf", "application/pdf")},
    )
    assert fake_pdf.status_code == 422
    binary = client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("malware.txt", b"hello\x00world", "text/plain")},
    )
    assert binary.status_code == 422


def test_unsafe_docx_archive_is_rejected(client: TestClient) -> None:
    session = register(client, "archive@example.com")
    project_id = create_project(client, session["access_token"])
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("../escape", "bad")
        archive.writestr("word/document.xml", "<xml />")
    response = client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers={"Authorization": f"Bearer {session['access_token']}"},
        files={"file": ("unsafe.docx", payload.getvalue(), "application/octet-stream")},
    )
    assert response.status_code == 422


def test_project_can_be_updated_and_deleted(client: TestClient) -> None:
    session = register(client, "project-crud@example.com")
    token = session["access_token"]
    project_id = create_project(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    updated = client.put(
        f"/api/v1/projects/{project_id}",
        headers=headers,
        json={"name": "Renamed", "description": "Updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert client.delete(f"/api/v1/projects/{project_id}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}", headers=headers).status_code == 404
