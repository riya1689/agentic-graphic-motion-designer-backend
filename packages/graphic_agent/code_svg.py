"""OpenAI/Gemini Code Image executor.

This is an isolated renderer adapter. It receives the planner's structured
plan, asks Gemini for SVG source inside a JSON response envelope, then
validates the source against the plan before exposing it as an artifact.
"""

from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from packages.execution.domain.contracts import ExecutionError, ExecutionRequest, ExecutionResult, ExecutionStatus, OutputAsset
from core.runtime_urls import public_api_url
from packages.ai.provider import active_provider, openai_model, openai_structured
from packages.provider_secrets.application.runtime import resolve_provider_secret
from packages.graphic_agent.compiler.prompt_compiler import compile_graphic_prompt
from packages.graphic_agent.rendering.illustrator import make_illustrator_compatible_svg
from packages.graphic_agent.rendering.colors import color_requirement_satisfied, normalize_color
from packages.graphic_agent.rendering.svg_renderer import SvgRenderer, SvgStructuralValidationError


def code_svg_directory(request_id: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    path = root / "runtime-data" / "graphic_agent" / request_id / "code"
    path.mkdir(parents=True, exist_ok=True)
    return path


def code_svg_path(request_id: str) -> Path:
    return code_svg_directory(request_id) / "design.svg"


class GeminiCodeSvgExecutor:
    provider_id = "openai_code"
    model_id = "code_image"

    _response_schema = {
        "type": "object",
        "properties": {
            "svg_code": {"type": "string"},
            "implementation_notes": {"type": "string"},
        },
        "required": ["svg_code"],
    }
    # Keep the planner contract complete, but never send binary asset data or
    # duplicated internal state to the model. This is comfortably below the
    # context limits of the configured OpenAI code-image model.
    _max_prompt_chars = 60000

    def __init__(self, *, model: str | None = None, api_key: str | None = None, client: Any = None) -> None:
        self.model = model or (
            openai_model("OPENAI_CODE_IMAGE_MODEL")
            if active_provider() == "openai"
            else os.getenv("CODE_IMAGE_MODEL", "gemini-3.5-flash-lite")
        )
        self._api_key = api_key or (
            resolve_provider_secret("openai", environment_names=("OPENAI_API_KEY",))
            if active_provider() == "openai"
            else resolve_provider_secret(
                "gemini",
                environment_names=("PLANNER_GEMINI_API_KEY", "GEMINI_API_KEY"),
            )
        )
        self._client = client

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.normalized_request.output.format != "svg":
            return self._failure(request, "OUTPUT_FORMAT_MISMATCH", "Code Image requires SVG output.")
        plan = request.metadata.get("execution_plan")
        metadata = getattr(plan, "metadata", {}) if plan else {}
        if not isinstance(metadata, dict) or not metadata.get("graphic_execution_spec"):
            return self._failure(request, "MISSING_PLANNER_PLAN", "Code Image requires the complete Planner execution plan.")
        if not self._api_key and self._client is None:
            return self._failure(request, "CODE_IMAGE_UNAVAILABLE", "The configured Code Image provider API key is missing.")

        self._print_plan(request, plan, metadata)
        prompt = self._prompt(request, plan, metadata)
        print(f"[CODE IMAGE] bounded prompt chars={len(prompt)}")
        try:
            svg_code = self._generate(prompt)
            svg_code = self._resolve_uploaded_asset_placeholders(svg_code, request, metadata)
            if request.metadata.get("hybrid_svg_foreground"):
                svg_code = self._remove_accidental_raster_layers(svg_code)
            if request.normalized_request.reference_assets:
                svg_code = make_illustrator_compatible_svg(
                    svg_code,
                    request.normalized_request.reference_assets,
                )
            svg_code = self._validate_svg(svg_code, request, metadata)
            path = code_svg_path(request.request_id)
            path.write_text(svg_code, encoding="utf-8")
        except SvgStructuralValidationError as exc:
            return self._failure(request, "CODE_IMAGE_VERIFICATION_FAILED", str(exc))
        except Exception as exc:
            return self._failure(request, "CODE_IMAGE_GENERATION_FAILED", str(exc))

        return ExecutionResult(
            request_id=request.request_id,
            status=ExecutionStatus.SUCCESS,
            provider=self.provider_id,
            model_id=self.model_id,
            output_assets=[OutputAsset(
                uri=public_api_url(
                    f"/api/manager/jobs/{request.request_id}/code/preview"
                ),
                format="svg",
                editable=True,
                native_editable=True,
                metadata={
                    "absolute_path": str(path),
                    "download_uri": public_api_url(
                        f"/api/manager/jobs/{request.request_id}/code/download"
                    ),
                    "provider_verified": True,
                    "media_type": "image",
                    "native_editable_evidence": "ai_generated_validated_svg",
                    "code_generated": True,
                },
            )],
            metadata={"renderer": "ai.code_svg", "absolute_path": str(path)},
        )

    def _generate(self, prompt: str) -> str:
        if active_provider() == "openai":
            payload = openai_structured(
                model=self.model,
                prompt=prompt,
                schema=self._response_schema,
                schema_name="code_image_svg",
            )
            code = payload.get("svg_code")
            if not isinstance(code, str) or not code.strip():
                raise ValueError("OpenAI returned no svg_code.")
            return self._strip_code_fence(code.strip())

        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        from google.genai import types

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=self._response_schema,
                        temperature=0.2,
                    ),
                )
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, dict):
                    payload = parsed
                elif parsed is not None and hasattr(parsed, "model_dump"):
                    payload = parsed.model_dump(mode="json")
                else:
                    payload = json.loads(response.text or "{}")
                code = payload.get("svg_code") if isinstance(payload, dict) else None
                if not isinstance(code, str) or not code.strip():
                    raise ValueError("Gemini returned no svg_code.")
                return self._strip_code_fence(code.strip())
            except Exception as exc:
                last_error = exc
                if attempt < 3 and any(token in str(exc).lower() for token in ("503", "429", "unavailable", "overload")):
                    time.sleep(2 ** (attempt - 1))
                else:
                    break
        raise RuntimeError(f"Gemini Code Image generation failed: {last_error}")

    @staticmethod
    def _strip_code_fence(value: str) -> str:
        match = re.fullmatch(r"```(?:svg|xml)?\s*(.*?)\s*```", value, flags=re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else value

    @staticmethod
    def _prompt(request: ExecutionRequest, plan, metadata: dict[str, Any]) -> str:
        compact_plan = GeminiCodeSvgExecutor._compact_plan_for_prompt(metadata)
        plan_json = json.dumps(compact_plan, ensure_ascii=False, separators=(",", ":"), default=str)
        hybrid_instruction = (
            "This is Hybrid SVG foreground mode: output only editable vector foreground elements. "
            "Do not create any raster background or <image> element; the system will add the raster background after this SVG is validated. "
        ) if request.metadata.get("hybrid_svg_foreground") else ""
        return (
            "You are the Code Image renderer in an agentic graphic design system. "
            + hybrid_instruction
            + "Generate one complete native SVG that fulfills every requirement in the Planner plan. "
            "Return only a JSON object matching the response schema; put the complete SVG source in svg_code. "
            "The SVG must contain visible required text, planned visual elements, correct colors, and the planned composition. "
            "Do not include markdown outside the JSON response. Do not embed generated raster images, scripts, foreignObject, external resources, JSON text, or explanatory text in the artwork. User-provided uploaded image assets may be embedded as data:image hrefs when the Planner specifies them.\n\n"
            + compile_graphic_prompt(request)
            + "\n\nAUTHORITATIVE PLANNER PLAN (internal instructions; fulfill it, do not print it in the artwork):\n"
            + plan_json
        )

    @classmethod
    def _compact_plan_for_prompt(cls, metadata: dict[str, Any]) -> dict[str, Any]:
        """Return a bounded, renderer-relevant view of Planner metadata.

        Planner metadata can contain repeated layout snapshots and uploaded
        images as base64 data URIs. Sending those values to the SVG model is
        both unnecessary and a common cause of context_length_exceeded. The
        actual asset bytes stay in the request and are restored after the
        model returns SVG using ``asset://uploaded-asset-N`` placeholders.
        """
        spec = metadata.get("graphic_execution_spec")
        compact: dict[str, Any] = {
            "job_summary": _prompt_value(metadata.get("job_summary")),
            "primary_job_type": _prompt_value(metadata.get("primary_job_type")),
            "target_output_format": _prompt_value(metadata.get("target_output_format")),
            "global_constraints": _prompt_value(metadata.get("global_constraints")),
            "execution_order": _prompt_value(metadata.get("execution_order")),
            "design_specification": cls._compact_value(metadata.get("design_specification")),
            "graphic_execution_spec": cls._compact_execution_spec(spec),
        }
        compact = {key: value for key, value in compact.items() if value not in (None, "", [], {})}
        encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":"), default=str)
        if len(encoded) <= cls._max_prompt_chars:
            return compact

        # Preserve the authoritative execution spec first. Optional design
        # provenance is removed before any requirement-bearing layer data.
        compact.pop("design_specification", None)
        encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":"), default=str)
        if len(encoded) <= cls._max_prompt_chars:
            return compact

        # This final fallback keeps all layers/elements but removes optional
        # planner narration. The request text and compiled natural-language
        # brief remain outside this JSON and are still sent to the model.
        return {
            "job_summary": compact.get("job_summary"),
            "global_constraints": compact.get("global_constraints"),
            "graphic_execution_spec": compact.get("graphic_execution_spec", {}),
        }

    @classmethod
    def _compact_execution_spec(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        result: dict[str, Any] = {}
        raw_assets = value.get("assets") if isinstance(value.get("assets"), list) else []
        asset_tokens = {
            str(item.get("uri")): f"asset://{item.get('id') or f'uploaded-asset-{index}'}"
            for index, item in enumerate(raw_assets, start=1)
            if isinstance(item, dict) and str(item.get("uri") or "").startswith("data:image/")
        }
        for key in ("version", "document", "palette", "assets", "layers"):
            if key not in value:
                continue
            if key == "document":
                result[key] = cls._compact_value(value[key], max_string=300)
            elif key == "palette":
                result[key] = cls._compact_value(value[key], max_string=300)
            elif key == "assets":
                result[key] = cls._compact_assets(value[key])
            elif key == "layers":
                result[key] = [
                    cls._compact_layer(item, asset_tokens)
                    for item in value[key]
                    if isinstance(item, dict)
                ]
            else:
                result[key] = cls._compact_value(value[key], max_string=300)
        return result

    @classmethod
    def _compact_assets(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        assets: list[dict[str, Any]] = []
        for index, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                continue
            asset_id = str(item.get("id") or f"uploaded-asset-{index}")
            assets.append({
                "id": asset_id,
                "type": _prompt_value(item.get("type") or item.get("kind") or "image"),
                "name": _prompt_value(item.get("name")),
                "description": _prompt_value(item.get("description")),
                "required": bool(item.get("required", True)),
                "renderer_reference": f"asset://{asset_id}",
            })
        return assets

    @classmethod
    def _compact_layer(cls, value: dict[str, Any], asset_tokens: dict[str, str] | None = None) -> dict[str, Any]:
        result = {
            key: cls._compact_value(value.get(key), max_string=1200)
            for key in ("id", "name", "visible", "locked")
            if value.get(key) not in (None, "")
        }
        result["elements"] = [
            cls._compact_element(item, asset_tokens)
            for item in value.get("elements", [])
            if isinstance(item, dict)
        ]
        return result

    @classmethod
    def _compact_element(cls, value: dict[str, Any], asset_tokens: dict[str, str] | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key in (
            "id", "type", "name", "content", "subject", "asset_id", "z_index",
            "placement", "style", "typography", "geometry", "fit", "requirement_reference",
        ):
            if key in value and value[key] not in (None, "", {}, []):
                result[key] = cls._compact_value(value[key], max_string=3000)
        raw_asset_uri = value.get("asset_uri")
        if raw_asset_uri:
            if str(raw_asset_uri).startswith("data:image/"):
                result["asset_reference"] = (asset_tokens or {}).get(
                    str(raw_asset_uri),
                    "asset://uploaded-asset-1",
                )
            else:
                result["asset_reference"] = cls._compact_value(raw_asset_uri, max_string=300)
        children = value.get("children")
        if isinstance(children, list) and children:
            result["children"] = [
                cls._compact_element(item, asset_tokens)
                for item in children
                if isinstance(item, dict)
            ]
        return result

    @classmethod
    def _compact_value(cls, value: Any, *, max_string: int = 2000) -> Any:
        if isinstance(value, str):
            if value.startswith("data:image/"):
                return "[uploaded image bytes omitted; use the declared asset renderer_reference]"
            return value if len(value) <= max_string else value[:max_string] + "…"
        if isinstance(value, dict):
            return {
                str(key): cls._compact_value(nested, max_string=max_string)
                for key, nested in value.items()
                if key not in {"uri", "path", "raw_prompt", "layout_specification", "planner_graphic_execution_spec"}
            }
        if isinstance(value, list):
            return [cls._compact_value(item, max_string=max_string) for item in value[:200]]
        return value

    @staticmethod
    def _resolve_uploaded_asset_placeholders(
        svg_code: str,
        request: ExecutionRequest,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Restore local uploaded image bytes after model generation.

        The model only sees short ``asset://uploaded-asset-N`` references. The
        real data URI is inserted locally, so binary data never consumes the
        model's input context and the existing asset verification remains
        authoritative.
        """
        resolved = svg_code
        assets = list(request.normalized_request.reference_assets or [])
        for asset in request.normalized_request.input_assets or []:
            if getattr(asset, "uri", None) and all(getattr(existing, "uri", None) != asset.uri for existing in assets):
                assets.append(asset)

        asset_map: dict[str, str] = {}
        for index, asset in enumerate(assets, start=1):
            uri = getattr(asset, "uri", None)
            if not uri or not str(uri).startswith("data:image/"):
                continue
            asset_id = f"uploaded-asset-{index}"
            asset_map[asset_id] = str(uri)

        # Preserve planner-assigned asset ids when they are available. This
        # covers plans that use ids such as ``brand-logo`` instead of the
        # request-order id used by the fallback mapping above.
        execution_spec = (metadata or {}).get("graphic_execution_spec", {})
        for index, item in enumerate(execution_spec.get("assets", []) if isinstance(execution_spec, dict) else [], start=1):
            if not isinstance(item, dict):
                continue
            uri = item.get("uri")
            if not (isinstance(uri, str) and uri.startswith("data:image/")) and index <= len(assets):
                candidate = getattr(assets[index - 1], "uri", None)
                uri = candidate if isinstance(candidate, str) and candidate.startswith("data:image/") else None
            if isinstance(uri, str) and uri.startswith("data:image/"):
                asset_id = str(item.get("id") or f"uploaded-asset-{index}")
                asset_map[asset_id] = uri
                asset_map.setdefault(f"uploaded-asset-{index}", uri)

        if not asset_map:
            return resolved

        resolved = re.sub(
            r"(?:asset|data-asset)://([A-Za-z0-9_.:-]+)",
            lambda match: asset_map.get(match.group(1))
            or (next(iter(asset_map.values())) if len(asset_map) == 1 else match.group(0)),
            resolved,
            flags=re.IGNORECASE,
        )
        resolved = re.sub(
            r"(href\s*=\s*[\"'])(uploaded-asset-[A-Za-z0-9_.:-]+)([\"'])",
            lambda match: f"{match.group(1)}{asset_map.get(match.group(2), match.group(2))}{match.group(3)}",
            resolved,
            flags=re.IGNORECASE,
        )
        return resolved

    @staticmethod
    def _print_plan(request: ExecutionRequest, plan, metadata: dict[str, Any]) -> None:
        steps = getattr(plan, "steps", []) or []
        print("[CODE IMAGE] Planner plan received")
        print(f"[CODE IMAGE] request_id={request.request_id} steps={len(steps)}")
        for step in steps:
            print(f"[CODE IMAGE] step={step.step_id} operation={step.operation}")
        specification = metadata.get("design_specification") or {}
        print(f"[CODE IMAGE] concept={specification.get('concept') or metadata.get('job_summary') or 'unspecified'}")
        print(f"[CODE IMAGE] required_text={request.normalized_request.text}")
        print(f"[CODE IMAGE] target_format={request.normalized_request.output.format}")

    @staticmethod
    def _validate_svg(svg_code: str, request: ExecutionRequest, metadata: dict[str, Any]) -> str:
        svg_code = GeminiCodeSvgExecutor._normalize_svg_colors(svg_code)
        try:
            root = ET.fromstring(svg_code)
        except ET.ParseError as exc:
            raise SvgStructuralValidationError(f"Gemini returned malformed SVG: {exc}") from exc
        if root.tag.rsplit("}", 1)[-1] != "svg":
            raise SvgStructuralValidationError("Gemini output root must be svg.")
        lowered = svg_code.lower()
        for forbidden in ("<script", "<foreignobject", "javascript:", " onload=", " onclick="):
            if forbidden in lowered:
                raise SvgStructuralValidationError(f"Gemini SVG contains forbidden content: {forbidden.strip()}")
        allowed_assets = {
            asset.uri
            for asset in request.normalized_request.reference_assets
            if asset.uri and str(asset.uri).startswith("data:image/")
        }
        for element in root.iter():
            href = element.attrib.get("href") or element.attrib.get("{http://www.w3.org/1999/xlink}href")
            if not href:
                continue
            if str(href).startswith("data:image/") and href not in allowed_assets:
                raise SvgStructuralValidationError("SVG contains an unapproved embedded image asset.")
            if str(href).startswith(("http://", "https://")):
                raise SvgStructuralValidationError("SVG cannot reference external image resources.")
        SvgRenderer().validate(svg_code, required_text=request.normalized_request.text)
        SvgRenderer.validate_required_asset_layers(svg_code, request.normalized_request.reference_assets)

        document = metadata.get("graphic_execution_spec", {}).get("document", {})
        expected_width = document.get("width")
        expected_height = document.get("height")
        if expected_width and str(root.attrib.get("width")) not in {str(expected_width), f"{expected_width}px"}:
            raise SvgStructuralValidationError(f"SVG width must match Planner width {expected_width}.")
        if expected_height and str(root.attrib.get("height")) not in {str(expected_height), f"{expected_height}px"}:
            raise SvgStructuralValidationError(f"SVG height must match Planner height {expected_height}.")

        plan_values = [
            str(element.get("content"))
            for layer in metadata.get("graphic_execution_spec", {}).get("layers", [])
            for element in (layer.get("elements", []) if isinstance(layer, dict) else [])
            if isinstance(element, dict) and element.get("content")
        ]
        rendered_text = " ".join(root.itertext())
        if plan_values and any(value not in rendered_text for value in plan_values):
            raise SvgStructuralValidationError("SVG does not contain all Planner text content.")

        for color in request.normalized_request.colors:
            if not color_requirement_satisfied(color, svg_code):
                raise SvgStructuralValidationError(f"Required color {color} is missing from SVG.")
        return svg_code

    @staticmethod
    def _remove_accidental_raster_layers(svg_code: str) -> str:
        """Keep Hybrid's foreground vector-only before composition.

        Hybrid SVG owns the raster background in a separate composition step.
        If the model nevertheless emits an accidental ``<image>`` element in
        the foreground, remove only that node. Uploaded-image requests do not
        set this mode and retain their existing asset behavior.
        """
        root = ET.fromstring(svg_code)
        for parent in root.iter():
            for child in list(parent):
                if child.tag.rsplit("}", 1)[-1].lower() == "image":
                    parent.remove(child)
        return ET.tostring(root, encoding="unicode", short_empty_elements=True)

    @staticmethod
    def _normalize_svg_colors(svg_code: str) -> str:
        """Convert recognized semantic color literals to valid SVG colors."""
        attribute_pattern = re.compile(
            r"((?:fill|stroke|color|stop-color|flood-color|lighting-color|style)\s*=\s*)(['\"])(.*?)(\2)",
            re.IGNORECASE | re.DOTALL,
        )

        def replace_attribute(match: re.Match[str]) -> str:
            value = match.group(3)
            for semantic, canonical in sorted(SEMANTIC_COLOR_REPLACEMENTS.items(), key=lambda item: -len(item[0])):
                value = re.sub(rf"(?<![\w-]){re.escape(semantic)}(?![\w-])", canonical, value, flags=re.IGNORECASE)
            return f"{match.group(1)}{match.group(2)}{value}{match.group(4)}"

        return attribute_pattern.sub(replace_attribute, svg_code)

    @staticmethod
    def _failure(request: ExecutionRequest, code: str, message: str) -> ExecutionResult:
        return ExecutionResult(
            request_id=request.request_id,
            status=ExecutionStatus.FAILED,
            provider="openai_code",
            model_id="code_image",
            error=ExecutionError(code, message),
        )


SEMANTIC_COLOR_REPLACEMENTS = {
    "deep navy": "#0b1020",
    "dark navy": "#0b1020",
    "electric blue": "#2563eb",
}


def _prompt_value(value: Any) -> Any:
    """Keep prompt metadata scalar and prevent accidental binary expansion."""
    if isinstance(value, str) and value.startswith("data:image/"):
        return "[uploaded image bytes omitted]"
    return value
