import hashlib
from pathlib import Path

import pytest

from research.evidence import EvidenceRetentionStore, compute_sha256


def test_store_artifact_writes_file_and_sha256(tmp_path: Path) -> None:
    store = EvidenceRetentionStore(tmp_path)
    content = b"Hello CH Core v2"

    artifact = store.store_artifact(
        case_id="test-case-01",
        artifact_id="sample-evidence",
        content=content,
        file_extension="txt",
        metadata={"source": "unit-test"},
    )

    stored_path = tmp_path / "test-case-01" / "sample-evidence.txt"
    assert stored_path.exists()
    assert stored_path.read_bytes() == content
    assert artifact.file_name == "sample-evidence.txt"
    assert artifact.file_size_bytes == len(content)
    assert artifact.sha256_hash == hashlib.sha256(content).hexdigest()
    assert artifact.sha256_hash == compute_sha256(stored_path)
    assert artifact.metadata == {"source": "unit-test"}
    assert artifact.captured_at.endswith("Z")


def test_store_artifact_is_idempotent_for_identical_content(tmp_path: Path) -> None:
    store = EvidenceRetentionStore(tmp_path)
    content = b"same bytes twice"

    first = store.store_artifact("case-a", "artifact-1", content, "bin")
    second = store.store_artifact("case-a", "artifact-1", content, "bin")

    assert first.sha256_hash == second.sha256_hash
    assert (tmp_path / "case-a" / "artifact-1.bin").read_bytes() == content


def test_store_artifact_rejects_hash_collision(tmp_path: Path) -> None:
    store = EvidenceRetentionStore(tmp_path)
    store.store_artifact("case-a", "artifact-1", b"original", "bin")

    with pytest.raises(FileExistsError, match="Artifact collision"):
        store.store_artifact("case-a", "artifact-1", b"tampered", "bin")
