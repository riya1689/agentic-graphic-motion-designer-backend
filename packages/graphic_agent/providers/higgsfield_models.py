"""
Higgsfield Image Model Registry

RESPONSIBILITY:

- Define Graphic Agent allowed Higgsfield image models
- Resolve frontend-selected model IDs
- Apply backend default model
- Reject unsupported / disabled models

IMPORTANT:

This file contains MODEL CONFIGURATION / POLICY only.

NO:
- Manager logic
- Planner logic
- Graphic workflow execution
- CLI execution
- MCP execution
- image generation
- verification
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


# ============================================================
# MODEL DEFINITION
# ============================================================

@dataclass(frozen=True)
class HiggsfieldImageModel:
    """
    One allowed Higgsfield image-generation model.

    model_id:
        Internal/frontend canonical identifier.

    job_type:
        Exact Higgsfield CLI job_type.

    display_name:
        Human-readable name.

    enabled:
        Allows model to be disabled without removing code.
    """

    model_id: str

    job_type: str

    display_name: str

    enabled: bool = True


# ============================================================
# DEFAULT MODEL
# ============================================================

DEFAULT_HIGGSFIELD_IMAGE_MODEL = (
    "nano_banana_flash"
)


# ============================================================
# MODEL REGISTRY
# ============================================================
#
# IMPORTANT:
#
# Keys use the SAME canonical identifiers that frontend sends.
#
# Future model add/remove happens here.
# ============================================================

HIGGSFIELD_IMAGE_MODELS: Dict[
    str,
    HiggsfieldImageModel,
] = {

    "nano_banana_flash":
        HiggsfieldImageModel(
            model_id="nano_banana_flash",
            job_type="nano_banana_flash",
            display_name="Nano Banana 2",
            enabled=True,
        ),

    "nano_banana_pro":
        HiggsfieldImageModel(
            model_id="nano_banana_pro",
            job_type="nano_banana_pro",
            display_name="Nano Banana Pro",
            enabled=True,
        ),

    "seedream_v4_5":
        HiggsfieldImageModel(
            model_id="seedream_v4_5",
            job_type="seedream_v4_5",
            display_name="Seedream 4.5",
            enabled=True,
        ),

    "seedream_v5_lite":
        HiggsfieldImageModel(
            model_id="seedream_v5_lite",
            job_type="seedream_v5_lite",
            display_name="Seedream 5.0 Lite",
            enabled=True,
        ),

}


# ============================================================
# RESOLVE MODEL
# ============================================================

def resolve_higgsfield_image_model(
    model_id: Optional[str],
) -> HiggsfieldImageModel:
    """
    Resolve and validate a frontend-selected image model.

    Rules:

    1. Missing model
           ↓
       backend default

    2. Unknown model
           ↓
       reject

    3. Disabled model
           ↓
       reject

    4. Valid model
           ↓
       return canonical model definition
    """

    normalized_model_id = (
        model_id or DEFAULT_HIGGSFIELD_IMAGE_MODEL
    ).strip().lower()


    model = HIGGSFIELD_IMAGE_MODELS.get(
        normalized_model_id
    )


    if model is None:

        allowed_models = ", ".join(
            get_enabled_higgsfield_image_model_ids()
        )

        raise ValueError(
            "Unsupported Higgsfield image model "
            f"'{normalized_model_id}'. "
            f"Allowed models: {allowed_models}"
        )


    if not model.enabled:

        raise ValueError(
            "Higgsfield image model "
            f"'{normalized_model_id}' is currently disabled."
        )


    return model


# ============================================================
# ENABLED MODEL IDS
# ============================================================

def get_enabled_higgsfield_image_model_ids(
) -> List[str]:

    return [

        model.model_id

        for model in HIGGSFIELD_IMAGE_MODELS.values()

        if model.enabled

    ]