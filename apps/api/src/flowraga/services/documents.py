import hashlib
import shutil
import uuid
import zipfile
from asyncio import to_thread
from pathlib import Path, PurePosixPath

import aiofiles
import boto3
from botocore.config import Config
from docx import Document as DocxDocument
from fastapi import UploadFile
from pypdf import PdfReader

from flowraga.core.config import Settings

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class InvalidDocument(ValueError):
    pass


def _object_key(settings: Settings, storage_key: str) -> str:
    prefix = settings.s3_key_prefix.strip("/")
    return f"{prefix}/{storage_key}" if prefix else storage_key


def _s3_client(settings: Settings):
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
        ),
    )


async def store_upload(upload: UploadFile, settings: Settings) -> tuple[str, Path, int, str]:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_TYPES:
        raise InvalidDocument("Only PDF, TXT, Markdown, and DOCX files are supported")
    root = Path(settings.storage_root).resolve()  # noqa: ASYNC240 -- no filesystem access
    root.mkdir(parents=True, exist_ok=True)
    key = f"{uuid.uuid4().hex}{suffix}"
    destination = root / key
    digest = hashlib.sha256()
    size = 0
    try:
        async with aiofiles.open(destination, "xb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise InvalidDocument("File exceeds the upload size limit")
                digest.update(chunk)
                await target.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    if size == 0:
        destination.unlink(missing_ok=True)
        raise InvalidDocument("File is empty")
    return key, destination, size, digest.hexdigest()


async def persist_stored_file(
    settings: Settings, storage_key: str, path: Path, media_type: str, checksum: str
) -> None:
    if settings.storage_backend == "local":
        return

    def upload_object() -> None:
        with path.open("rb") as source:
            _s3_client(settings).upload_fileobj(
                source,
                settings.s3_bucket or "",
                _object_key(settings, storage_key),
                ExtraArgs={
                    "ContentType": media_type,
                    "Metadata": {"sha256": checksum},
                },
            )

    try:
        await to_thread(upload_object)
    except Exception as exc:
        raise InvalidDocument("The document could not be saved to object storage") from exc
    await to_thread(path.unlink, missing_ok=True)


def _inspect_docx(path: Path, settings: Settings) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > settings.max_archive_entries:
                raise InvalidDocument("DOCX archive contains too many entries")
            total = 0
            names = set()
            for entry in entries:
                parts = PurePosixPath(entry.filename).parts
                if entry.flag_bits & 0x1 or ".." in parts or entry.filename.startswith(("/", "\\")):
                    raise InvalidDocument("Unsafe DOCX archive")
                total += entry.file_size
                if total > settings.max_archive_uncompressed_bytes:
                    raise InvalidDocument("DOCX expands beyond the safety limit")
                if entry.compress_size and entry.file_size / entry.compress_size > 100:
                    raise InvalidDocument("DOCX compression ratio is unsafe")
                names.add(entry.filename)
            if "word/document.xml" not in names:
                raise InvalidDocument("DOCX signature is invalid")
    except zipfile.BadZipFile as exc:
        raise InvalidDocument("DOCX signature is invalid") from exc


def validate_and_extract(path: Path, settings: Settings) -> tuple[str, str]:
    suffix = path.suffix.lower()
    header = path.read_bytes()[:8]
    try:
        if suffix == ".pdf":
            if not header.startswith(b"%PDF-"):
                raise InvalidDocument("PDF signature is invalid")
            reader = PdfReader(path)
            if len(reader.pages) > 500:
                raise InvalidDocument("PDF exceeds the 500-page limit")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix == ".docx":
            if not header.startswith(b"PK"):
                raise InvalidDocument("DOCX signature is invalid")
            _inspect_docx(path, settings)
            document = DocxDocument(path)
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        else:
            raw = path.read_bytes()
            if b"\x00" in raw:
                raise InvalidDocument("Text file appears to be binary")
            text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidDocument("Text files must use UTF-8 encoding") from exc
    except InvalidDocument:
        raise
    except Exception as exc:
        raise InvalidDocument("The document could not be safely parsed") from exc
    return ALLOWED_TYPES[suffix], text.strip()


async def delete_stored_file(settings: Settings, storage_key: str) -> None:
    if settings.storage_backend == "s3":
        await to_thread(
            _s3_client(settings).delete_object,
            Bucket=settings.s3_bucket or "",
            Key=_object_key(settings, storage_key),
        )
        return
    def delete_local() -> None:
        root = Path(settings.storage_root).resolve()
        candidate = (root / storage_key).resolve()
        if candidate.parent == root:
            candidate.unlink(missing_ok=True)

    await to_thread(delete_local)


def delete_storage_tree(settings: Settings) -> None:
    shutil.rmtree(Path(settings.storage_root), ignore_errors=True)
