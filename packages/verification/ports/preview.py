"""Provider-neutral preview-rendering port."""

from __future__ import annotations

from typing import Protocol

from packages.verification.domain.visual import PreviewArtifact


class PreviewRendererPort(Protocol):
    def render(self, svg_text: str, *, source_artifact: str, output_reference: str) -> PreviewArtifact:
        ...
