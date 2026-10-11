"""Deterministic image verification using Pillow when available."""

from __future__ import annotations

from typing import List

from packages.execution.domain.contracts import OutputAsset
from packages.verification.domain.contracts import VerificationIssue
from packages.verification.strategies.common import local_path, normalize_format


class ImageVerifier:
    def verify_asset(
        self,
        asset: OutputAsset,
        requested_format: str,
        requested_size,
        *,
        allow_embedded_assets: bool = False,
    ) -> tuple[List[VerificationIssue], List[str], bool]:
        issues: List[VerificationIssue] = []
        checked = ["output_exists", "media_type", "format"]
        path = local_path(asset.uri)
        if path is None:
            if (asset.metadata or {}).get("provider_verified"):
                return [], checked + ["provider_result"], True
            metadata_path = (asset.metadata or {}).get("absolute_path")
            path = local_path(str(metadata_path)) if metadata_path else None
        if path is None:
            return (
                [VerificationIssue("output_uninspectable", "Remote image output cannot be inspected locally.")],
                checked,
                False,
            )
        if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
            return [VerificationIssue("missing_output", "Image output does not exist or is empty.")], checked, False

        if normalize_format(requested_format) == "svg" and path.suffix.lower() == ".svg":
            try:
                svg = path.read_text(encoding="utf-8")
            except Exception as exc:
                return [VerificationIssue("invalid_output", f"SVG output is unreadable: {exc}")], checked, False
            if "<svg" not in svg or "</svg>" not in svg:
                return [VerificationIssue("invalid_output", "Output is not a complete SVG document.")], checked, False
            has_embedded_image = "<image" in svg.lower() or "data:image/" in svg.lower()
            if has_embedded_image and not allow_embedded_assets:
                return [VerificationIssue("raster_embedded", "SVG contains an embedded raster image; native vector output is required.")], checked, False
            if "<path" not in svg and "<rect" not in svg and "<text" not in svg and "<circle" not in svg:
                return [VerificationIssue("invalid_output", "SVG contains no vector drawing primitives.")], checked, False
            declared_format = normalize_format(asset.format)
            if declared_format != "svg":
                return [VerificationIssue("format_mismatch", f"Declared {declared_format}, found svg.")], checked, True
            return [], checked + ["native_vector_objects"], True

        try:
            from PIL import Image

            with Image.open(path) as image:
                actual_format = normalize_format(image.format or "")
                actual_size = image.size
                image.verify()
        except Exception as exc:
            return [VerificationIssue("invalid_output", f"Image output is unreadable: {exc}")], checked, False

        declared_media = asset.metadata.get("media_type")
        if declared_media not in (None, "image"):
            issues.append(VerificationIssue("media_type_mismatch", "Output metadata does not identify image media."))
        declared_format = normalize_format(asset.format)
        if declared_format != actual_format:
            issues.append(VerificationIssue("format_mismatch", f"Declared {declared_format}, found {actual_format or 'unknown'}."))
        if actual_format != normalize_format(requested_format):
            issues.append(VerificationIssue("format_mismatch", f"Expected {requested_format}, found {actual_format or 'unknown'}."))
        if requested_size is not None:
            checked.append("dimensions")
            expected = (requested_size.width, requested_size.height)
            if actual_size != expected:
                issues.append(VerificationIssue("dimension_mismatch", f"Expected {expected[0]}x{expected[1]}, found {actual_size[0]}x{actual_size[1]}."))
        return issues, checked, True
