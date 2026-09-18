from fastapi.testclient import TestClient
from test_auth import register
from test_documents import create_project

from flowraga.services.evaluation import (
    aggregate_metrics,
    citation_metrics,
    retrieval_metrics,
    token_f1,
)


def test_deterministic_evaluation_metrics() -> None:
    assert token_f1("alpha beta", "alpha gamma") == 0.5
    assert retrieval_metrics(["a", "b"], ["b", "c"]) == {
        "retrieval_recall": 0.5,
        "retrieval_precision": 0.5,
    }
    citations = citation_metrics("Fact one [S1]. Fact two [S3].", 2)
    assert citations["citation_validity"] == 0.5
    assert citations["citation_coverage"] == 1.0
    assert aggregate_metrics([{"score": 0.5}, {"score": 1.0}]) == {"score": 0.75, "case_count": 2}


def test_evaluation_dataset_run_and_owner_isolation(client: TestClient) -> None:
    owner = register(client, "evaluation-owner@example.com")
    other = register(client, "evaluation-other@example.com")
    project_id = create_project(client, owner["access_token"])
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    dataset = client.post(
        f"/api/v1/projects/{project_id}/evaluations/datasets",
        headers=headers,
        json={"name": "Regression set", "description": "Core questions"},
    )
    assert dataset.status_code == 201, dataset.text
    dataset_id = dataset.json()["id"]
    case = client.post(
        f"/api/v1/projects/{project_id}/evaluations/datasets/{dataset_id}/cases",
        headers=headers,
        json={"question": "What is alpha?", "expected_answer": "Alpha is first."},
    )
    assert case.status_code == 201, case.text
    run = client.post(
        f"/api/v1/projects/{project_id}/evaluations/datasets/{dataset_id}/runs",
        headers=headers,
        json={"retrieval_mode": "hybrid", "top_k": 5, "similarity_threshold": 0.25},
    )
    assert run.status_code == 201, run.text
    assert run.json()["status"] == "queued"
    denied = client.get(
        f"/api/v1/projects/{project_id}/evaluations/datasets/{dataset_id}/cases",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert denied.status_code == 404
