from fastapi.testclient import TestClient
from test_auth import register
from test_documents import create_project

from flowraga.schemas.pipelines import PipelineConfiguration


def graph_configuration() -> dict:
    types = ["source", "chunk", "embed", "retrieve", "rerank", "generate", "evaluate"]
    return {
        "retrieval_mode": "hybrid",
        "top_k": 5,
        "similarity_threshold": 0.25,
        "rerank": True,
        "nodes": [
            {"id": value, "type": value, "label": value.title(), "x": index * 100, "y": 0}
            for index, value in enumerate(types)
        ],
        "edges": [
            {"id": f"{source}-{target}", "source": source, "target": target}
            for source, target in zip(types, types[1:], strict=False)
        ],
    }


def test_pipeline_graph_validation() -> None:
    valid = PipelineConfiguration.model_validate(graph_configuration())
    assert len(valid.nodes) == 7
    invalid = graph_configuration()
    invalid["edges"] = []
    try:
        PipelineConfiguration.model_validate(invalid)
        raise AssertionError("Disconnected graph was accepted")
    except ValueError as error:
        assert "connect source to generation" in str(error)


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
            "configuration": graph_configuration(),
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
