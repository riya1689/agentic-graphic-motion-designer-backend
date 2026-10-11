"""Gemini adapter for structured, specification-aware visual critique."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, List

from pydantic import BaseModel, Field, ValidationError

from packages.verification.domain.visual import (
    InspectionCategory,
    InspectionConfidence,
    InspectionSeverity,
    RequirementInspection,
    RequirementInspectionStatus,
    VisualCritiqueRequest,
    VisualInspectionIssue,
    VisualInspectionResult,
)
from packages.ai.provider import active_provider, openai_model, openai_multimodal_structured
from packages.provider_secrets.application.runtime import resolve_provider_secret


logger = logging.getLogger(__name__)


class _ProviderFinding(BaseModel):
    id: str | None = None
    category: InspectionCategory
    severity: InspectionSeverity
    message: str = Field(min_length=1, max_length=500)
    evidence: str = Field(min_length=1, max_length=800)
    affected_element: str | None = None
    affected_region: str | None = None
    requirement_reference: str | None = None
    confidence: InspectionConfidence = InspectionConfidence.MEDIUM


class _ProviderRequirement(BaseModel):
    requirement_reference: str = Field(min_length=1, max_length=300)
    status: RequirementInspectionStatus
    evidence: str = Field(min_length=1, max_length=800)
    confidence: InspectionConfidence = InspectionConfidence.MEDIUM


class _ProviderCritique(BaseModel):
    findings: List[_ProviderFinding] = Field(default_factory=list, max_length=15)
    requirements: List[_ProviderRequirement] = Field(default_factory=list, max_length=50)


# Gemini's structured-output endpoint is stricter than Pydantic JSON Schema:
# it rejects local $ref/anyOf constraints in this response shape. Keep the
# provider schema flat, then validate the returned payload with Pydantic.
_GEMINI_CRITIQUE_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "category": {"type": "string", "enum": [item.value for item in InspectionCategory]},
                    "severity": {"type": "string", "enum": [item.value for item in InspectionSeverity]},
                    "message": {"type": "string"},
                    "evidence": {"type": "string"},
                    "affected_element": {"type": "string"},
                    "affected_region": {"type": "string"},
                    "requirement_reference": {"type": "string"},
                    "confidence": {"type": "string", "enum": [item.value for item in InspectionConfidence]},
                },
                "required": ["id", "category", "severity", "message", "evidence", "affected_element", "affected_region", "requirement_reference", "confidence"],
            },
        },
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement_reference": {"type": "string"},
                    "status": {"type": "string", "enum": [item.value for item in RequirementInspectionStatus]},
                    "evidence": {"type": "string"},
                    "confidence": {"type": "string", "enum": [item.value for item in InspectionConfidence]},
                },
                "required": ["requirement_reference", "status", "evidence", "confidence"],
            },
        },
    },
    "required": ["findings", "requirements"],
}


class GeminiVisionInspectionAdapter:
    """Translate a provider-neutral critique request to Gemini structured JSON."""

    def __init__(self, *, model: str | None = None, max_findings: int = 15) -> None:
        self._model = model or os.getenv("GEMINI_VISION_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
        self._max_findings = max(1, min(max_findings, 15))
        self._client = None

    def inspect(self, request: VisualCritiqueRequest) -> VisualInspectionResult:
        try:
            data, mime_type = self._read_preview(request)
            logger.info("vision inspection started")
            prompt = self._prompt(request)
            if active_provider() == "openai":
                raw_payload = openai_multimodal_structured(
                    prompt=prompt,
                    image_bytes=data,
                    image_mime_type=mime_type,
                    model=openai_model("OPENAI_VISION_MODEL"),
                    schema=_GEMINI_CRITIQUE_SCHEMA,
                    schema_name="visual_critique",
                )
            else:
                from google import genai
                from google.genai import types

                response = self._get_client().models.generate_content(
                    model=self._model,
                    contents=[prompt, types.Part.from_bytes(data=data, mime_type=mime_type)],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=_GEMINI_CRITIQUE_SCHEMA,
                    ),
                )
                raw_payload = response.parsed or json.loads(response.text)
            payload = _ProviderCritique.model_validate(raw_payload)
            result = self._normalize(payload, request)
            logger.info("vision inspection completed: %s findings", len(result.issues))
            return result
        except Exception as exc:
            logger.warning("vision inspection unavailable: %s", exc)
            return VisualInspectionResult(
                render_success=False,
                source="vision",
                warnings=[f"Vision inspection unavailable: {exc}"],
            )

    def _get_client(self):
        if self._client is None:
            from google import genai
            api_key = resolve_provider_secret(
                "gemini",
                environment_names=("GEMINI_API_KEY",),
            )
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY is missing.")
            self._client = genai.Client(api_key=api_key)
        return self._client

    def _normalize(self, payload: _ProviderCritique, request: VisualCritiqueRequest) -> VisualInspectionResult:
        known_elements = {
            str(item.get("id"))
            for item in request.layout_specification.get("elements", [])
            if isinstance(item, dict) and item.get("id")
        }
        known_regions = {
            str(item.get("id"))
            for item in request.layout_specification.get("regions", [])
            if isinstance(item, dict) and item.get("id")
        }
        known_requirements = set(request.user_requirements)
        known_requirements.update(
            str(item.get("requirement"))
            for item in request.design_specification.get("requirement_coverage", [])
            if isinstance(item, dict) and item.get("requirement")
        )
        issues = []
        for finding in payload.findings[: self._max_findings]:
            issues.append(
                VisualInspectionIssue(
                    id=finding.id,
                    category=finding.category,
                    severity=finding.severity,
                    message=finding.message[:500],
                    evidence=finding.evidence[:800],
                    affected_element=finding.affected_element if finding.affected_element in known_elements else None,
                    affected_region=finding.affected_region if finding.affected_region in known_regions else None,
                    requirement_reference=finding.requirement_reference if finding.requirement_reference in known_requirements else None,
                    confidence=finding.confidence,
                    source="vision",
                )
            )
        requirements = [
            RequirementInspection(
                requirement_reference=item.requirement_reference,
                status=item.status,
                evidence=item.evidence[:800],
                confidence=item.confidence,
                source="vision",
            )
            for item in payload.requirements
            if item.requirement_reference in known_requirements
        ]
        return VisualInspectionResult(
            render_success=True,
            issues=issues,
            requirements=requirements,
            warnings=[],
            source="vision",
        )

    @staticmethod
    def _read_preview(request: VisualCritiqueRequest):
        reference = request.preview.reference
        if not reference:
            raise FileNotFoundError("Preview has no readable reference.")
        path = Path(reference)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("Preview reference is not accessible.")
        mime_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        return path.read_bytes(), mime_type

    @staticmethod
    def _prompt(request: VisualCritiqueRequest) -> str:
        return """You are a professional graphic design visual critic and art director.

Evaluate the rendered preview against the supplied intended design. Do not redesign
the artwork and do not provide chain-of-thought. Return concise JSON only.

Inspect communication, visual hierarchy, composition, typography, color, assets,
and explicit user requirements. Separate user requirements from designer decisions.
Use only observable visual evidence. If an item cannot be determined reliably,
use uncertain or low confidence. Return at most 15 findings.

DESIGN BRIEF:
""" + json.dumps(request.design_brief, ensure_ascii=False) + """

DESIGN SPECIFICATION:
""" + json.dumps(request.design_specification, ensure_ascii=False) + """

LAYOUT SPECIFICATION:
""" + json.dumps(request.layout_specification, ensure_ascii=False) + """

USER REQUIREMENTS:
""" + json.dumps(request.user_requirements, ensure_ascii=False) + """

INSPECTION CRITERIA:
""" + json.dumps(request.inspection_criteria, ensure_ascii=False)
