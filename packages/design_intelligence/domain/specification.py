"""Provider-neutral design-intelligence contracts.

These models describe design decisions, not SVG commands, provider models, or
filesystem artifacts.  They are intentionally extensible so design types can
be added through reasoning and skills rather than application branches.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.request_contract.domain.schema import AssetReference, NormalizedRequest, SizeSpec


class ContentPriority(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUPPORTING = "supporting"
    CTA = "cta"
    METADATA = "metadata"
    DECORATIVE = "decorative"


class DesignContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_id: str = Field(min_length=1)
    value: str = Field(min_length=1)
    priority: ContentPriority
    required: bool = True
    prominence: int = Field(default=3, ge=1, le=5)
    position_intent: Optional[str] = None
    grouping: Optional[str] = None
    reading_order: Optional[int] = Field(default=None, ge=1)
    emphasis: Optional[str] = None


class DesignBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_type: str = Field(min_length=1)
    purpose: Optional[str] = None
    audience: Optional[str] = None
    context: str = Field(min_length=1)
    platform: Optional[str] = None
    orientation: Optional[str] = None
    canvas: Optional[SizeSpec] = None
    primary_message: Optional[str] = None
    secondary_messages: List[str] = Field(default_factory=list)
    supporting_information: List[str] = Field(default_factory=list)
    call_to_action: Optional[str] = None
    required_text: List[str] = Field(default_factory=list)
    optional_text: List[str] = Field(default_factory=list)
    required_colors: List[str] = Field(default_factory=list)
    forbidden_colors: List[str] = Field(default_factory=list)
    required_assets: List[AssetReference] = Field(default_factory=list)
    required_logo: Optional[str] = None
    required_elements: List[str] = Field(default_factory=list)
    user_constraints: List[str] = Field(default_factory=list)
    brand_constraints: List[str] = Field(default_factory=list)
    visual_mood: Optional[str] = None
    preferred_style: Optional[str] = None
    tone: Optional[str] = None
    references: List[AssetReference] = Field(default_factory=list)
    output_format: str = Field(min_length=1)
    editable_requirement: bool = False
    quality_requirement: Optional[str] = None
    # General-purpose context, not a template selector. These fields preserve
    # why the artifact exists and where it will be read.
    communication_goal: Optional[str] = None
    content_density: Optional[str] = None
    visual_tone: Optional[str] = None
    format_constraints: List[str] = Field(default_factory=list)
    reading_environment: Optional[str] = None
    information_priority: Optional[str] = None
    interaction_goal: Optional[str] = None


class ArtDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: Optional[str] = None
    mood: Optional[str] = None
    tone: Optional[str] = None
    visual_language: Optional[str] = None
    imagery_direction: Optional[str] = None
    decorative_direction: Optional[str] = None
    shape_language: Optional[str] = None
    texture: Optional[str] = None
    lighting: Optional[str] = None
    depth: Optional[str] = None
    abstraction_level: Optional[str] = None
    visual_density: Optional[str] = None
    brand_character: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class HierarchyItem(BaseModel):
    content_id: str = Field(min_length=1)
    priority: ContentPriority
    prominence: int = Field(default=3, ge=1, le=5)
    contrast_expectation: Optional[str] = None
    scale_expectation: Optional[str] = None
    position_intent: Optional[str] = None
    grouping: Optional[str] = None
    weight: Optional[str] = None
    whitespace_intent: Optional[str] = None


class VisualHierarchy(BaseModel):
    primary_focal_point: Optional[str] = None
    primary_visual_anchor: Optional[str] = None
    secondary_focal_points: List[str] = Field(default_factory=list)
    reading_path: Optional[str] = None
    whitespace_intent: Optional[str] = None
    items: List[HierarchyItem] = Field(default_factory=list)


class ContentRegion(BaseModel):
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    relationship: Optional[str] = None


class CompositionIntent(BaseModel):
    strategy: Optional[str] = None
    grid: Optional[str] = None
    alignment: Optional[str] = None
    balance: Optional[str] = None
    symmetry: Optional[str] = None
    focal_placement: Optional[str] = None
    negative_space: Optional[str] = None
    density: Optional[str] = None
    visual_flow: Optional[str] = None
    safe_area: Optional[str] = None
    margins: Optional[str] = None
    reading_direction: Optional[str] = None
    content_regions: List[ContentRegion] = Field(default_factory=list)


class TypographyLevel(BaseModel):
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    font_category: Optional[str] = None
    pairing_role: Optional[str] = None
    weight: Optional[str] = None
    scale: Optional[str] = None
    alignment: Optional[str] = None
    line_height: Optional[str] = None
    letter_spacing: Optional[str] = None
    max_text_width: Optional[str] = None
    wrapping: Optional[str] = None
    readability: Optional[str] = None
    font_personality: Optional[str] = None
    casing: Optional[str] = None
    text_density: Optional[str] = None
    contrast_intent: Optional[str] = None
    # Numeric overrides are intentionally optional: semantic typography remains
    # the source of truth, while revision patches can make bounded adjustments.
    font_size: Optional[float] = Field(default=None, gt=0, le=512)
    letter_spacing_value: Optional[float] = Field(default=None, ge=-20, le=50)
    line_height_value: Optional[float] = Field(default=None, gt=0.5, le=3.0)


class TypographyIntent(BaseModel):
    display: Optional[TypographyLevel] = None
    body: Optional[TypographyLevel] = None
    hierarchy_levels: List[TypographyLevel] = Field(default_factory=list)
    font_pairing_intent: Optional[str] = None
    readability_requirements: List[str] = Field(default_factory=list)


class ColorSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    background: Optional[str] = None
    # A treatment is an explicit design decision, not an implicit renderer
    # default.  Examples: "solid", "gradient", "photo", "texture".
    background_treatment: Optional[str] = None
    surface: Optional[str] = None
    primary: Optional[str] = None
    secondary: Optional[str] = None
    accent: Optional[str] = None
    text: Optional[str] = None
    muted_text: Optional[str] = None
    cta: Optional[str] = None
    border: Optional[str] = None
    decorative: List[str] = Field(default_factory=list)
    required_colors: List[str] = Field(default_factory=list)
    forbidden_colors: List[str] = Field(default_factory=list)
    additional_roles: Dict[str, str] = Field(default_factory=dict)
    contrast_intent: Optional[str] = None
    dominance: Optional[str] = None
    temperature: Optional[str] = None
    saturation: Optional[str] = None
    harmony: Optional[str] = None
    accent_usage: Optional[str] = None
    background_foreground_relationship: Optional[str] = None

    @model_validator(mode="after")
    def validate_roles(self):
        roles = [
            self.background, self.surface, self.primary, self.secondary,
            self.accent, self.text, self.muted_text, self.cta, self.border,
        ]
        if not any(value for value in roles) and not self.decorative and not self.additional_roles:
            raise ValueError("color system must define at least one semantic color role")
        return self


class RequirementCoverage(BaseModel):
    requirement: str = Field(min_length=1)
    specification_path: str = Field(min_length=1)
    status: str = "covered"
    evidence: Optional[str] = None
    source: Literal["user_requirement", "designer_decision"] = "user_requirement"


class DesignAssetIntent(BaseModel):
    asset_type: str = Field(min_length=1)
    role: str = Field(min_length=1)
    treatment: Optional[str] = None
    placement_intent: Optional[str] = None
    source: Literal["user_provided", "generated", "native", "none"] = "none"


class AssetStrategy(BaseModel):
    imagery_required: bool = False
    visual_anchor: Optional[str] = None
    assets: List[DesignAssetIntent] = Field(default_factory=list)


class GraphicDesignTokens(BaseModel):
    spacing: Dict[str, str] = Field(default_factory=dict)
    margins: Optional[str] = None
    section_spacing: Optional[str] = None
    component_spacing: Optional[str] = None
    radius: Dict[str, str] = Field(default_factory=dict)
    border_width: Dict[str, str] = Field(default_factory=dict)
    shadow_intent: Optional[str] = None
    opacity: Dict[str, str] = Field(default_factory=dict)
    density: Optional[str] = None


class DesignSpecification(BaseModel):
    """Design intent consumed by a later execution-specification adapter."""

    model_config = ConfigDict(extra="forbid")

    brief: DesignBrief
    design_type: str = Field(min_length=1)
    concept: str = Field(min_length=1)
    art_direction: ArtDirection = Field(default_factory=ArtDirection)
    content_hierarchy: List[DesignContent] = Field(default_factory=list)
    visual_hierarchy: VisualHierarchy = Field(default_factory=VisualHierarchy)
    composition: CompositionIntent = Field(default_factory=CompositionIntent)
    typography: TypographyIntent = Field(default_factory=TypographyIntent)
    color_system: ColorSystem
    assets: List[AssetReference] = Field(default_factory=list)
    asset_strategy: AssetStrategy = Field(default_factory=AssetStrategy)
    design_tokens: GraphicDesignTokens = Field(default_factory=GraphicDesignTokens)
    # Optional normalized layout and visual-element decisions from the
    # planner. These are semantic scene intent, not SVG/provider payloads.
    layout_plan: Dict[str, Any] = Field(default_factory=dict)
    visual_elements: List[Dict[str, Any]] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    requirement_coverage: List[RequirementCoverage] = Field(default_factory=list)
    user_requirements: List[str] = Field(default_factory=list)
    designer_decisions: List[str] = Field(default_factory=list)
    decision_sources: Dict[str, str] = Field(default_factory=dict)
    # Safe, renderer-independent layout adjustments produced by Phase 8.
    # This is deliberately not an SVG or JSONPath patch.
    layout_overrides: Dict[str, Dict[str, float | str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_consistency(self):
        if self.design_type != self.brief.design_type:
            raise ValueError("design_type must match the design brief")
        ids = {item.content_id for item in self.content_hierarchy}
        for item in self.visual_hierarchy.items:
            if item.content_id not in ids:
                raise ValueError(f"visual hierarchy references unknown content: {item.content_id}")
        coverage = {item.requirement for item in self.requirement_coverage}
        for value in self.brief.required_text:
            if value not in coverage:
                raise ValueError(f"required text is not traceable: {value}")
        if not self.user_requirements:
            raise ValueError("user_requirements must preserve explicit request requirements")
        return self

    @classmethod
    def from_normalized_request(cls, request: NormalizedRequest) -> "DesignSpecification":
        return design_specification_from_request(request)


def _priority_for_text(value: str, index: int, total: int) -> ContentPriority:
    lowered = value.lower()
    if any(token in lowered for token in ("register", "sign up", "buy", "shop", "learn more", "apply", "contact")):
        return ContentPriority.CTA
    if any(token in lowered for token in ("date", "january", "february", "march", "april", "may ", "june", "july", "august", "september", "october", "november", "december", "venue", "location", "doors open")):
        return ContentPriority.METADATA
    if index == 0:
        return ContentPriority.PRIMARY
    if index < 3 or total <= 3:
        return ContentPriority.SECONDARY
    return ContentPriority.SUPPORTING


def design_brief_from_request(request: NormalizedRequest) -> DesignBrief:
    text = list(request.text)
    cta = next((value for value in text if _priority_for_text(value, text.index(value), len(text)) == ContentPriority.CTA), None)
    secondary = [value for value in text[1:] if value != cta and _priority_for_text(value, text.index(value), len(text)) != ContentPriority.METADATA]
    supporting = [value for value in text[1:] if value != cta and value not in secondary]
    return DesignBrief(
        design_type=request.design_type or "custom design",
        purpose=request.purpose,
        audience=request.audience,
        context=request.context_prompt,
        platform=request.additional_requirements.get("platform"),
        orientation=request.additional_requirements.get("orientation"),
        canvas=request.size,
        primary_message=text[0] if text else request.purpose,
        secondary_messages=secondary,
        supporting_information=supporting,
        call_to_action=cta,
        required_text=text,
        required_colors=list(request.colors),
        required_assets=list(request.reference_assets),
        required_elements=list(request.additional_requirements.get("required_elements") or []),
        user_constraints=list(request.additional_requirements.get("requirements") or []),
        visual_mood=request.additional_requirements.get("mood"),
        preferred_style=request.style,
        tone=request.additional_requirements.get("tone"),
        references=list(request.reference_assets),
        output_format=request.output.format,
        editable_requirement=request.output.editable_required or request.output.native_editable_required,
        quality_requirement=request.quality_preferences.get("quality"),
        communication_goal=request.purpose or request.context_prompt,
        visual_tone=request.style,
        format_constraints=[request.output.format],
        reading_environment=request.additional_requirements.get("platform"),
        interaction_goal="conversion" if cta else None,
    )


def _asset_role_for_request(prompt: str) -> str:
    lowered = prompt.lower()
    if "logo" in lowered or "brand mark" in lowered:
        return "user-provided logo layer"
    if "background" in lowered or "backdrop" in lowered:
        return "user-provided background layer"
    if "product" in lowered:
        return "user-provided product image layer"
    if "reference" in lowered or "inspiration" in lowered:
        return "user-provided visual reference"
    return "supporting visual reference"


def _asset_placement_for_request(prompt: str) -> str:
    lowered = prompt.lower()
    for placement in ("top-left", "top-right", "bottom-left", "bottom-right", "center", "left", "right"):
        if placement in lowered:
            return f"place the user asset at {placement} as requested"
    if "background" in lowered or "backdrop" in lowered:
        return "cover the full canvas behind all other layers"
    return "preserve relevance to the primary communication"


def design_specification_from_request(request: NormalizedRequest) -> DesignSpecification:
    brief = design_brief_from_request(request)
    design_type = (brief.design_type or "custom design").lower()
    composition_strategy = _composition_strategy(design_type, brief.platform, brief.orientation)
    content = [
        DesignContent(
            content_id=f"content-{index + 1}",
            value=value,
            priority=_priority_for_text(value, index, len(request.text)),
            prominence=5 if index == 0 else 3,
            position_intent="primary focal region" if index == 0 else None,
            reading_order=index + 1,
            emphasis="dominant" if index == 0 else "restrained",
        )
        for index, value in enumerate(request.text)
    ]
    if brief.call_to_action:
        for item in content:
            if item.value == brief.call_to_action:
                item.prominence = 4
                item.position_intent = "clear action region"
    hierarchy = VisualHierarchy(
        primary_focal_point=content[0].content_id if content else None,
        primary_visual_anchor="primary message" if content else None,
        secondary_focal_points=[item.content_id for item in content[1:3]],
        reading_path="primary message → supporting information → CTA",
        whitespace_intent="preserve clear separation around required content",
        items=[
            HierarchyItem(
                content_id=item.content_id,
                priority=item.priority,
                prominence=item.prominence,
                position_intent=item.position_intent,
                weight="dominant" if item.priority == ContentPriority.PRIMARY else "supporting",
                whitespace_intent="clear separation",
            )
            for item in content
        ],
    )
    colors = list(request.colors)
    color_system = ColorSystem(
        primary=colors[0] if colors else None,
        secondary=colors[1] if len(colors) > 1 else None,
        background=colors[0] if colors else "#ffffff",
        text="#111111",
        required_colors=colors,
        contrast_intent="high contrast for required text",
        dominance="primary color supports the focal point",
        temperature="preserve user-specified color temperature" if colors else "balanced neutral base",
        saturation="controlled accent saturation",
        harmony="coherent relationship between required colors",
        accent_usage="reserve accent for focal or CTA emphasis",
        background_foreground_relationship="clear foreground/background separation",
    )
    if not colors:
        color_system = ColorSystem(background="#ffffff", text="#111111")
    typography = TypographyIntent(
        display=TypographyLevel(name="display", purpose="primary message", scale="largest", readability="high", font_personality="confident and distinctive", casing="preserve requested copy", contrast_intent="high"),
        body=TypographyLevel(name="body", purpose="supporting information", scale="readable", readability="high", font_personality="clear and neutral", casing="natural", contrast_intent="comfortable"),
        hierarchy_levels=[
            TypographyLevel(name="headline", purpose="primary message", scale="largest", weight="strong", text_density="low"),
            TypographyLevel(name="supporting", purpose="secondary and supporting information", scale="medium", text_density="comfortable"),
            TypographyLevel(name="metadata", purpose="dates, venue, and context", scale="small", weight="restrained", text_density="compact"),
            TypographyLevel(name="cta", purpose="call to action", scale="prominent", weight="strong", casing="clear emphasis"),
        ],
    )
    user_requirements = list(request.text) + list(request.colors) + list(brief.user_constraints)
    if not user_requirements:
        # Preserve an unstructured request as an auditable user requirement
        # until an AI reasoner extracts more granular fields.
        user_requirements = [brief.context]
    coverage = [
        RequirementCoverage(
            requirement=value,
            specification_path=f"content_hierarchy[{index}]",
            evidence="required user text preserved",
        )
        for index, value in enumerate(request.text)
    ]
    coverage.extend(
        RequirementCoverage(
            requirement=color,
            specification_path="color_system.required_colors",
            evidence="explicit user color preserved",
        )
        for color in request.colors
    )
    coverage.extend(
        RequirementCoverage(
            requirement=constraint,
            specification_path="constraints",
            evidence="explicit user constraint preserved",
        )
        for constraint in brief.user_constraints
    )
    return DesignSpecification(
        brief=brief,
        design_type=brief.design_type,
        concept=_concept_for_request(brief, composition_strategy),
        art_direction=ArtDirection(
            style=request.style,
            mood=brief.visual_mood,
            tone=brief.tone,
            visual_language="clear, intentional, and context-appropriate",
            imagery_direction="use imagery only when it supports the communication goal",
            decorative_direction="restrained elements that reinforce hierarchy",
            shape_language="coherent shapes related to the selected visual language",
            texture="minimal unless the brief requires material texture",
            depth="subtle depth supporting separation",
            abstraction_level="appropriate to the design context",
            visual_density="content-led rather than decoration-led",
        ),
        content_hierarchy=content,
        visual_hierarchy=hierarchy,
        composition=CompositionIntent(
            strategy=composition_strategy,
            alignment="adapt to content priorities",
            balance="purposeful balance",
            negative_space="preserve readable breathing room",
            density="appropriate to the communication context",
            safe_area="keep required content inside the readable canvas area",
            margins="comfortable outer margins",
            reading_direction="follow the natural language reading direction",
            content_regions=[
                ContentRegion(name="primary", purpose="primary communication", relationship="dominates the focal region"),
                ContentRegion(name="supporting", purpose="secondary and supporting information", relationship="supports the primary region"),
                ContentRegion(name="action", purpose="call to action", relationship="clear and discoverable after supporting content"),
            ],
        ),
        typography=typography,
        color_system=color_system,
        assets=list(request.reference_assets),
        asset_strategy=AssetStrategy(
            imagery_required=bool(request.reference_assets),
            visual_anchor="user-provided reference asset" if request.reference_assets else "primary message",
        assets=[
                DesignAssetIntent(
                    asset_type=asset.kind,
                    role=_asset_role_for_request(request.context_prompt),
                    placement_intent=_asset_placement_for_request(request.context_prompt),
                    source="user_provided",
                )
                for asset in request.reference_assets
            ],
        ),
        design_tokens=GraphicDesignTokens(
            spacing={"space_xs": "tight", "space_sm": "compact", "space_md": "comfortable", "space_lg": "generous", "space_xl": "section-level"},
            margins="comfortable",
            section_spacing="generous",
            component_spacing="consistent",
            radius={"radius_sm": "subtle", "radius_md": "moderate", "radius_lg": "prominent when context supports it"},
            border_width={"border_thin": "restrained", "border_medium": "emphasis"},
            shadow_intent="subtle separation only when needed",
            opacity={"muted": "reduced", "decorative": "controlled"},
            density="balanced",
        ),
        constraints=list(brief.user_constraints),
        requirement_coverage=coverage,
        user_requirements=user_requirements,
        designer_decisions=[
            "Prioritize the first required text as the primary communication anchor.",
            "Use a clear reading path from primary message through supporting content to action.",
            "Keep decoration subordinate to communication.",
        ],
        decision_sources={
            "brief": "user",
            "content_hierarchy": "user_and_system_default",
            "color_system": "user_and_system_default",
            "composition": "system_default",
            "visual_hierarchy": "system_default",
            "typography": "system_default",
            "art_direction": "system_default",
            "asset_strategy": "user_and_system_default",
        },
    )


def _composition_strategy(design_type: str, platform: str | None, orientation: str | None) -> str:
    """Choose a contextual baseline; an AI planner may refine this decision."""
    if "banner" in design_type or orientation == "landscape":
        return "split"
    if "certificate" in design_type:
        return "whitespace_driven"
    if "invitation" in design_type:
        return "centered"
    if "infographic" in design_type or "presentation" in design_type:
        return "modular"
    if "thumbnail" in design_type or "product" in design_type or "social" in design_type:
        return "focal_centered"
    return "intent-driven composition"


def _concept_for_request(brief: DesignBrief, strategy: str) -> str:
    style = brief.preferred_style or "context-appropriate"
    audience = f" for {brief.audience}" if brief.audience else ""
    composition = strategy.replace("_", " ")
    if composition.endswith(" composition"):
        composition = composition[:-12]
    return (
        f"A {style} {brief.design_type}{audience} using a {composition} composition, "
        "with the primary message as the communication anchor and supporting information sequenced for clarity."
    )
