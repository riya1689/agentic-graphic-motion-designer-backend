"""
Graphic Artifact Store

RESPONSIBILITY:

- Persist formatted output artifact metadata
- Provide preview/download URLs
- Load stored artifact information for API endpoints

IMPORTANT:

This file does NOT:
- generate images
- decide tools
- contain planner logic
- contain manager logic
"""

from __future__ import annotations

import json

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict

from core.runtime_urls import public_api_base_url


# ============================================================
# RUNTIME ROOT
# ============================================================

RUNTIME_ROOT = (
    Path("runtime-data")
    / "graphic_agent"
)

# ============================================================
# PUBLIC BASE URL
# ============================================================
#
# COMMENT:
# Graphic artifact preview/download endpoints are served by the public
# backend instance. Standalone graphic-agent deployments can override this
# with PUBLIC_API_BASE_URL without changing artifact or rendering logic.
# ============================================================

PUBLIC_BASE_URL = public_api_base_url()


# ============================================================
# ARTIFACT RECORD
# ============================================================

@dataclass
class GraphicArtifactRecord:
    job_id: str
    format: str
    filename: str
    absolute_path: str
    mime_type: str
    preview_url: str
    download_url: str


# ============================================================
# PATH HELPERS
# ============================================================

def get_job_root(
    job_id: str,
) -> Path:
    return RUNTIME_ROOT / job_id


def get_output_dir(
    job_id: str,
) -> Path:
    output_dir = (
        get_job_root(job_id)
        / "output"
    )
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    return output_dir


def get_artifact_meta_path(
    job_id: str,
) -> Path:
    artifacts_dir = (
        get_job_root(job_id)
        / "artifacts"
    )
    artifacts_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    return artifacts_dir / "artifact.json"


# ============================================================
# URL HELPERS
# ============================================================

def build_preview_url(
    job_id: str,
) -> str:
    return (
        f"{PUBLIC_BASE_URL}"
        f"/api/graphic/artifacts/{job_id}/preview"
    )


def build_download_url(
    job_id: str,
) -> str:
    return (
        f"{PUBLIC_BASE_URL}"
        f"/api/graphic/artifacts/{job_id}/download"
    )


# ============================================================
# SAVE / LOAD
# ============================================================

def save_artifact_record(
    record: GraphicArtifactRecord,
) -> Dict[str, Any]:
    meta_path = get_artifact_meta_path(
        record.job_id
    )

    meta_path.write_text(
        json.dumps(
            asdict(record),
            indent=2,
        ),
        encoding="utf-8",
    )

    return asdict(record)


def load_artifact_record(
    job_id: str,
) -> GraphicArtifactRecord:
    meta_path = get_artifact_meta_path(
        job_id
    )

    if not meta_path.exists():
        raise FileNotFoundError(
            f"Artifact metadata not found for job_id={job_id}"
        )

    data = json.loads(
        meta_path.read_text(
            encoding="utf-8"
        )
    )

    return GraphicArtifactRecord(
        **data
    )
