from fastapi.testclient import TestClient
from test_auth import register
from test_documents import create_project

from flowraga.main import app
from flowraga.models.dependencies import (
    get_embedding_provider,
    get_generation_provider,
    get_reranking_provider,
)
from flowraga.models.embeddings import DeterministicEmbeddingProvider
from flowraga.models.providers import GenerationProvider


class FakeGenerationProvider(GenerationProvider):
    async def generate(self, messages):
        return "Grounded answer [S1]."

    async def stream(self, messages):
        yield await self.generate(messages)


class FakeReranker:
    async def rerank(self, query, documents):
        return [(index, 1.0 - index / 10) for index in range(len(documents))]


def test_question_without_evidence_skips_generation_and_is_owner_isolated(
    client: TestClient,
) -> None:
    app.dependency_overrides[get_embedding_provider] = lambda: DeterministicEmbeddingProvider()
    app.dependency_overrides[get_generation_provider] = FakeGenerationProvider
    app.dependency_overrides[get_reranking_provider] = FakeReranker
    owner = register(client, "question-owner@example.com")
    other = register(client, "question-other@example.com")
    project_id = create_project(client, owner["access_token"])
    response = client.post(
        f"/api/v1/projects/{project_id}/ask",
        json={"question": "What is documented?"},
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["generation_status"] == "skipped_no_evidence"
    assert response.json()["sources"] == []
    conversation_id = response.json()["conversation_id"]
    conversations = client.get(
        f"/api/v1/projects/{project_id}/conversations",
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    )
    assert conversations.status_code == 200
    assert conversations.json()[0]["id"] == conversation_id
    detail = client.get(
        f"/api/v1/projects/{project_id}/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    )
    assert [message["role"] for message in detail.json()["messages"]] == [
        "user",
        "assistant",
    ]
    message_id = response.json()["message_id"]
    feedback = client.put(
        f"/api/v1/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}/feedback",
        json={"rating": 1, "comment": "Useful evidence"},
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    )
    assert feedback.status_code == 200
    assert feedback.json()["rating"] == 1
    exported = client.get(
        f"/api/v1/projects/{project_id}/conversations/{conversation_id}/export",
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    )
    assert exported.status_code == 200
    assert "# What is documented?" in exported.text
    private = client.get(
        f"/api/v1/projects/{project_id}/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert private.status_code == 404
    denied = client.post(
        f"/api/v1/projects/{project_id}/ask",
        json={"question": "Reveal it"},
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert denied.status_code == 404
    deleted = client.delete(
        f"/api/v1/projects/{project_id}/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    )
    assert deleted.status_code == 204
