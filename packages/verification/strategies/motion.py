"""Deterministic motion verification without requiring ffprobe."""

from __future__ import annotations

from typing import Any, Dict, List

from packages.execution.domain.contracts import OutputAsset
from packages.verification.domain.contracts import VerificationIssue
from packages.verification.strategies.common import local_path, normalize_format


class MotionVerifier:
    supported_formats = {"mp4", "mov", "webm", "mkv"}

    def verify_asset(
        self,
        asset: OutputAsset,
        requested_format: str,
        requested_size,
        metadata: Dict[str, Any],
    ) -> tuple[List[VerificationIssue], List[str], bool]:
        issues: List[VerificationIssue] = []
        checked = ["output_exists", "media_type", "format"]
        path = local_path(asset.uri)
        if path is None:
            return [VerificationIssue("output_uninspectable", "Remote motion output cannot be inspected locally without media tooling.")], checked, False
        if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
            return [VerificationIssue("missing_output", "Motion output does not exist or is empty.")], checked, False

        actual_format = normalize_format(str(metadata.get("actual_format") or path.suffix))
        if actual_format not in self.supported_formats:
            issues.append(VerificationIssue("invalid_output", "Motion output does not have a supported container format."))
        if actual_format != normalize_format(requested_format):
            issues.append(VerificationIssue("format_mismatch", f"Expected {requested_format}, found {actual_format or 'unknown'}."))
        if metadata.get("media_type") not in (None, "video", "motion"):
            issues.append(VerificationIssue("media_type_mismatch", "Motion metadata does not identify video output."))
        if requested_size is not None:
            checked.append("dimensions")
            dimensions = metadata.get("dimensions")
            if dimensions is None:
                return [VerificationIssue("output_uninspectable", "Motion dimensions require explicit metadata when ffprobe is unavailable.")], checked, False
            expected = (requested_size.width, requested_size.height)
            actual = tuple(dimensions)
            if actual != expected:
                issues.append(VerificationIssue("dimension_mismatch", f"Expected {expected[0]}x{expected[1]}, found {actual[0]}x{actual[1]} ."))
        required_duration = metadata.get("required_duration_seconds")
        if required_duration is not None:
            checked.append("duration")
            duration = metadata.get("duration_seconds")
            if duration is None:
                return [VerificationIssue("output_uninspectable", "Motion duration requires explicit metadata when ffprobe is unavailable.")], checked, False
            if float(duration) <= 0 or float(duration) < float(required_duration):
                issues.append(VerificationIssue("duration_mismatch", "Motion duration does not satisfy the requirement."))
        return issues, checked, True
