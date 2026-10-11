"""Small provider boundary for structured OpenAI/Gemini model calls.

OpenAI is the preferred provider when ``AI_PROVIDER=openai`` or when
``AI_PROVIDER=auto`` and an OpenAI key is present. Gemini remains an optional
fallback so provider migration does not leak into business logic.
"""

from __future__ import annotations

import json
import os
import re
import base64
from typing import Any

from packages.provider_secrets.application.runtime import resolve_provider_secret


def active_provider() -> str:
    configured = os.getenv("AI_PROVIDER", "openai").strip().lower()
    if configured == "auto":
        return "openai" if resolve_provider_secret(
            "openai",
            environment_names=("OPENAI_API_KEY",),
        ) else "gemini"
    return configured if configured in {"openai", "gemini"} else "openai"


def openai_available() -> bool:
    return bool(resolve_provider_secret("openai", environment_names=("OPENAI_API_KEY",))) and active_provider() == "openai"


def openai_model(env_name: str, default: str = "gpt-5") -> str:
    return os.getenv(env_name, default).strip() or default


def openai_structured(
    *,
    prompt: str,
    system_instruction: str | None = None,
    model: str | None = None,
    schema: dict[str, Any] | None = None,
    schema_name: str = "structured_output",
) -> dict[str, Any]:
    """Call OpenAI Responses API and decode a JSON-schema response."""
    api_key = resolve_provider_secret("openai", environment_names=("OPENAI_API_KEY",))
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    input_messages: list[dict[str, Any]] = []
    if system_instruction:
        input_messages.append({"role": "system", "content": system_instruction})
    input_messages.append({"role": "user", "content": prompt})
    response_format = {
        "type": "json_schema",
        "name": re.sub(r"[^A-Za-z0-9_-]", "_", schema_name)[:64],
        "schema": schema or {"type": "object", "additionalProperties": True},
        "strict": False,
    }
    response = client.responses.create(
        model=model or openai_model("OPENAI_MODEL"),
        input=input_messages,
        text={"format": response_format},
    )
    text = getattr(response, "output_text", None)
    if not text:
        raise RuntimeError("OpenAI returned an empty structured response.")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise RuntimeError("OpenAI structured response must be a JSON object.")
    return payload


def openai_multimodal_structured(
    *,
    prompt: str,
    image_bytes: bytes,
    image_mime_type: str,
    model: str | None = None,
    schema: dict[str, Any] | None = None,
    schema_name: str = "visual_assessment",
) -> dict[str, Any]:
    """Call OpenAI Responses API with one local image and JSON output."""
    api_key = resolve_provider_secret("openai", environment_names=("OPENAI_API_KEY",))
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing.")
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    image_url = f"data:{image_mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    response = client.responses.create(
        model=model or openai_model("OPENAI_VISION_MODEL"),
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": image_url},
            ],
        }],
        text={"format": {
            "type": "json_schema",
            "name": re.sub(r"[^A-Za-z0-9_-]", "_", schema_name)[:64],
            "schema": schema or {"type": "object", "additionalProperties": True},
            "strict": False,
        }},
    )
    text = getattr(response, "output_text", None)
    if not text:
        raise RuntimeError("OpenAI returned an empty visual assessment.")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise RuntimeError("OpenAI visual assessment must be a JSON object.")
    return payload


def openai_generate_raster_image(
    *,
    prompt: str,
    model: str | None = None,
    size: str = "1024x1024",
) -> tuple[bytes, str]:
    """Generate one raster image and return embedded bytes plus MIME type."""
    api_key = resolve_provider_secret("openai", environment_names=("OPENAI_API_KEY",))
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.images.generate(
        model=model or openai_model("OPENAI_BACKGROUND_IMAGE_MODEL", "gpt-image-1"),
        prompt=prompt,
        size=size,
    )
    items = getattr(response, "data", None) or []
    first = items[0] if items else None
    encoded = getattr(first, "b64_json", None) if first is not None else None
    if not isinstance(encoded, str) or not encoded:
        raise RuntimeError("OpenAI raster generator returned no embedded image data.")
    output_format = str(getattr(first, "output_format", None) or "png").lower()
    mime_type = {
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "webp": "image/webp",
    }.get(output_format, "image/png")
    return base64.b64decode(encoded), mime_type
