# packages/prompt_to_json_agent/domain/schema.py

# উদ্দেশ্য:
# 1. Core Graphic Design schema define করা
# 2. Schema-তে না থাকা user-provided requirements preserve করা
# 3. Prompt ↔ JSON coverage verification result define করা

from typing import List, Literal, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


# ================================================================
# LAYER MODEL
# ================================================================

class LayerItem(BaseModel):

    layer_name: str = Field(
        ...,
        description="লেয়ারের নাম অথবা 'USER_NOT_PROVIDED'"
    )

    layer_type: Literal[
        "vector_shape",
        "raster_image",
        "text_frame",
        "adjustment",
        "group",
        "USER_NOT_PROVIDED"
    ] = Field(
        ...,
        description="লেয়ারের ধরন"
    )

    visual_description: str = Field(
        ...,
        description="লেয়ারের বর্ণনা অথবা 'USER_NOT_PROVIDED'"
    )


# ================================================================
# MAIN GRAPHIC DESIGN SPECIFICATION
# ================================================================

class GraphicDesignSpec(BaseModel):

    # ============================================================
    # IMPORTANT:
    #
    # Core schema stable থাকবে।
    #
    # User যদি এমন কোনো graphic design requirement দেয়
    # যেটা নিচের fixed schema-তে define করা নেই,
    # তাহলে সেই information হারাবে না।
    #
    # সেটি additional_requirements এর মধ্যে যাবে।
    #
    # Example:
    #
    # "camera_angle": "low-angle"
    # "lighting": "cinematic"
    # "depth_of_field": "shallow"
    # ============================================================

    model_config = ConfigDict(
        extra="allow"
    )


    # ============================================================
    # CORE FIELD 1:
    # Asset Type
    # ============================================================

    asset_type: Literal[
        "image",
        "motion"
    ] = Field(
        ...,
        description="Asset type: image অথবা motion"
    )


    # ============================================================
    # CORE FIELD 2:
    # Target Software
    # ============================================================

    target_software: Literal[
        "adobe_illustrator",
        "adobe_photoshop",
        "after_effects",
        "USER_NOT_PROVIDED"
    ] = Field(
        ...,
        description=(
            "Target software অথবা "
            "'USER_NOT_PROVIDED'"
        )
    )


    # ============================================================
    # CORE FIELD 3:
    # Canvas Dimensions
    # ============================================================

    canvas_dimensions: str = Field(
        ...,
        description=(
            "Canvas dimensions যেমন 1920x1080 "
            "অথবা 'USER_NOT_PROVIDED'"
        )
    )


    # ============================================================
    # CORE FIELD 4:
    # Color Palette
    # ============================================================

    color_palette: List[str] = Field(
        ...,
        description=(
            "Color palette যেমন ['#000000', '#FFFFFF'] "
            "অথবা ['USER_NOT_PROVIDED']"
        )
    )


    # ============================================================
    # CORE FIELD 5:
    # Primary Subject
    # ============================================================

    primary_subject: str = Field(
        ...,
        description=(
            "Main visual subject অথবা "
            "'USER_NOT_PROVIDED'"
        )
    )


    # ============================================================
    # CORE FIELD 6:
    # Editable Typography
    # ============================================================

    editable_typography: List[str] = Field(
        ...,
        description=(
            "Editable typography / copy text অথবা "
            "['USER_NOT_PROVIDED']"
        )
    )


    # ============================================================
    # CORE FIELD 7:
    # Layer Breakdown
    # ============================================================

    layers: List[LayerItem] = Field(
        ...,
        description=(
            "Design layer breakdown অথবা "
            "USER_NOT_PROVIDED layer item"
        )
    )


    # ============================================================
    # CORE FIELD 8:
    # Motion Duration
    #
    # image হলে 0.0 থাকতে পারবে
    # motion হলে later validator > 0 ensure করবে
    # ============================================================

    motion_duration_sec: float = Field(
        default=0.0,
        description="Motion duration in seconds"
    )


    # ============================================================
    # NEW:
    # DYNAMIC / ADDITIONAL USER REQUIREMENTS
    #
    # User prompt-এ দেওয়া কিন্তু predefined schema-তে
    # না থাকা যেকোনো meaningful specification এখানে যাবে।
    #
    # IMPORTANT:
    # এগুলো Missing Field নয়।
    #
    # Example:
    #
    # {
    #     "camera_angle": "low-angle",
    #     "lighting": "cinematic",
    #     "fog": "volumetric blue fog",
    #     "depth_of_field": "shallow",
    #     "composition": "rule of thirds",
    #     "perspective": "dramatic"
    # }
    # ============================================================

    additional_requirements: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Any explicit graphic design requirement supplied "
            "by the user that does not belong to the predefined "
            "core fields."
        )
    )


# ================================================================
# PROMPT ↔ JSON COVERAGE VERIFICATION MODEL
#
# এই model verifier LLM-এর output control করবে।
#
# Example:
#
# {
#     "all_user_requirements_captured": false,
#     "missing_requirements": [
#         "volumetric blue fog"
#     ],
#     "verification_notes": [
#         "Fog requirement was not represented in JSON."
#     ]
# }
# ================================================================

class PromptCoverageResult(BaseModel):

    # ============================================================
    # True = user prompt-এর সব explicit requirement JSON-এ আছে
    # False = কিছু requirement বাদ গেছে
    # ============================================================

    all_user_requirements_captured: bool = Field(
        ...,
        description=(
            "True only when every explicit meaningful "
            "user requirement exists somewhere in the JSON."
        )
    )


    # ============================================================
    # Prompt-এ ছিল কিন্তু JSON-এ নেই এমন requirement list
    # ============================================================

    missing_requirements: List[str] = Field(
        default_factory=list,
        description=(
            "Explicit user requirements that were present "
            "in the original prompt but missing from JSON."
        )
    )


    # ============================================================
    # Optional verifier explanation
    # ============================================================

    verification_notes: List[str] = Field(
        default_factory=list,
        description=(
            "Optional notes explaining the verification result."
        )
    )