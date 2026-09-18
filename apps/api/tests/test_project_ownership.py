from fastapi.testclient import TestClient
from test_auth import register


def test_projects_are_isolated_by_owner(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    other = register(client, "other@example.com")

    created = client.post(
        "/api/v1/projects",
        json={"name": "Private knowledge base", "description": "Owner-only data"},
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    owner_view = client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    )
    assert owner_view.status_code == 200

    other_view = client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert other_view.status_code == 404

    other_list = client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert other_list.status_code == 200
    assert other_list.json() == []
