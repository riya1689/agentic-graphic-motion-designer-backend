"""Native SVG rendering infrastructure."""

from .svg_renderer import (
    SvgRenderCompiler,
    SvgRenderer,
    SvgStructuralValidationError,
)

__all__ = ["SvgRenderCompiler", "SvgRenderer", "SvgStructuralValidationError"]
