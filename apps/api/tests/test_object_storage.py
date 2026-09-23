from pathlib import Path

import pytest

from flowraga.core.config import Settings
from flowraga.services import documents


class FakeS3:
    def __init__(self) -> None:
        self.uploaded = None
        self.deleted = None

    def upload_fileobj(self, source, bucket, key, ExtraArgs):
        self.uploaded = (source.read(), bucket, key, ExtraArgs)

    def delete_object(self, **kwargs):
        self.deleted = kwargs


@pytest.mark.asyncio
async def test_s3_upload_and_delete(monkeypatch, tmp_path: Path) -> None:
    fake = FakeS3()
    monkeypatch.setattr(documents, "_s3_client", lambda _: fake)
    settings = Settings(
        storage_backend="s3",
        s3_bucket="documents",
        s3_endpoint_url="https://account.r2.cloudflarestorage.com",
        s3_access_key_id="access",
        s3_secret_access_key="secret",
        s3_key_prefix="private/uploads",
    )
    path = tmp_path / "document.txt"
    path.write_bytes(b"permanent content")

    await documents.persist_stored_file(
        settings, "abc.txt", path, "text/plain", "known-checksum"
    )

    assert not path.exists()
    assert fake.uploaded[0] == b"permanent content"
    assert fake.uploaded[1:3] == ("documents", "private/uploads/abc.txt")
    assert fake.uploaded[3]["ContentType"] == "text/plain"
    assert fake.uploaded[3]["Metadata"] == {"sha256": "known-checksum"}

    await documents.delete_stored_file(settings, "abc.txt")
    assert fake.deleted == {"Bucket": "documents", "Key": "private/uploads/abc.txt"}
