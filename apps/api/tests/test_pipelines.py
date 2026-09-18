from fastapi.testclient import TestClient
from test_auth import register
from test_documents import create_project


def test_pipeline_lifecycle_export_and_isolation(client: TestClient) -> None:
    owner = register(client, "pipeline-owner@example.com")
    other = register(client, "pipeline-other@example.com")
    project_id = create_project(client, owner["access_token"])
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    created = client.post(
        f"/api/v1/projects/{project_id}/pipelines",
        headers=headers,
        json={
            "name": "Balanced",
            "configuration": {
                "retrieval_mode": "hybrid",
                "top_k": 5,
                "similarity_threshold": 0.25,
                "rerank": True,
            },
        },
    )
    assert created.status_code == 201, created.text
    pipeline_id = created.json()["id"]
    activated = client.post(
        f"/api/v1/projects/{project_id}/pipelines/{pipeline_id}/activate", headers=headers
    )
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True
    exported = client.get(f"/api/v1/projects/{project_id}/pipelines/export/all", headers=headers)
    assert exported.status_code == 200
    assert exported.json()["format"] == "flowraga-pipelines-v1"
    denied = client.get(
        f"/api/v1/projects/{project_id}/pipelines",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert denied.status_code == 404


def test_pipeline_configuration_is_bounded(client: TestClient) -> None:
    owner = register(client, "pipeline-validation@example.com")
    project_id = create_project(client, owner["access_token"])
    response = client.post(
        f"/api/v1/projects/{project_id}/pipelines",
        headers={"Authorization": f"Bearer {owner['access_token']}"},
        json={"name": "Unsafe", "configuration": {"top_k": 1000}},
    )
    assert response.status_code == 422
