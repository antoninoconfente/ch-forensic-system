"""Minimal Proof of Value: retain an image, run unverified vision analysis, retain the result."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))

from research.evidence import EvidenceManifest, EvidenceRetentionStore
from research.vision import OpenAIControlledVisionClient

CASE_ID = "pov-case-01"
IMAGE_FIXTURE = ROOT / "data" / "fixtures" / "pov-object.jpg"
STORE_DIR = ROOT / "data" / "manifests"
PROMPT = (
    "Describe visible material, form, and surface features of this object as visual hypotheses only. "
    "Do not assert identity, authenticity, dating, or provenance."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is missing. Add it to .env and rerun.")
        return 1

    if not IMAGE_FIXTURE.exists():
        print(f"Missing fixture image: {IMAGE_FIXTURE}")
        return 1

    store = EvidenceRetentionStore(STORE_DIR)
    image_bytes = IMAGE_FIXTURE.read_bytes()
    image_artifact = store.store_artifact(
        case_id=CASE_ID,
        artifact_id="pov-object",
        content=image_bytes,
        file_extension="jpg",
        metadata={"source": "pov-fixture", "role": "visual-input"},
    )

    retained_image = STORE_DIR / CASE_ID / image_artifact.file_name
    client = OpenAIControlledVisionClient()
    observation = client.analyze_image(str(retained_image), PROMPT)

    observation_artifact = store.store_artifact(
        case_id=CASE_ID,
        artifact_id="pov-vision-observation",
        content=observation.model_dump_json(indent=2).encode("utf-8"),
        file_extension="json",
        metadata={
            "source": "openai-controlled-vision",
            "status": observation.status,
            "model_name": observation.model_name,
        },
    )

    manifest = EvidenceManifest(
        case_id=CASE_ID,
        created_at=utc_now(),
        artifacts=[image_artifact, observation_artifact],
    )
    store.store_artifact(
        case_id=CASE_ID,
        artifact_id="pov-manifest",
        content=manifest.model_dump_json(indent=2).encode("utf-8"),
        file_extension="json",
        metadata={"role": "manifest"},
    )

    description = observation.normalized_observations.get("description") or ""
    print("PoV complete")
    print(f"case_id={CASE_ID}")
    print(f"image_sha256={image_artifact.sha256_hash}")
    print(f"observation_sha256={observation_artifact.sha256_hash}")
    print(f"status={observation.status}")
    print(f"model_name={observation.model_name}")
    print(f"description_preview={description[:280]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
