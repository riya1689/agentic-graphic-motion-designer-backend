"""
Higgsfield Image Tool

RESPONSIBILITY:

Graphic Agent
    ↓
Higgsfield Image Tool
    ↓
Higgsfield CLI Bridge
"""

from typing import Any, Dict

from packages.graphic_agent.artifacts.image_store import (
    save_remote_image_artifact,
)
from packages.graphic_agent.bridges.higgsfield_cli import (
    HiggsfieldGraphicCLI,
)
from packages.graphic_agent.tools.base import GraphicTool


# ============================================================
# HIGGSFIELD IMAGE TOOL
# ============================================================

class HiggsfieldImageTool(GraphicTool):

    tool_id = "higgsfield_image"


    # ========================================================
    # EXECUTE
    # ========================================================

    def execute(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute Higgsfield image generation.

        IMPORTANT:

        Graphic Agent passes ONE positional payload dictionary
        through the common tool interface.

        Therefore this tool must accept:

            tool.execute(payload)

        Do NOT make the arguments keyword-only here.
        """

        # ========================================================
        # READ TOOL INPUT
        # ========================================================

        job_id = str(
            payload.get(
                "job_id",
                "",
            )
        )

        prompt = str(
            payload.get(
                "prompt",
                "",
            )
        )

        image_model = str(
            payload.get(
                "image_model",
                "",
            )
        )

        image_job_type = str(
            payload.get(
                "image_job_type",
                "",
            )
        )


        # ========================================================
        # VALIDATE INPUT
        # ========================================================

        if not job_id:

            raise ValueError(
                "HiggsfieldImageTool requires job_id."
            )


        if not prompt:

            raise ValueError(
                "HiggsfieldImageTool requires prompt."
            )


        if not image_model:

            raise ValueError(
                "HiggsfieldImageTool requires image_model."
            )


        if not image_job_type:

            raise ValueError(
                "HiggsfieldImageTool requires image_job_type."
            )


        # ========================================================
        # PROVIDER JOB TYPE
        # ========================================================

        job_type = image_job_type


        print(
            f"[HIGGSFIELD IMAGE TOOL] Model: "
            f"{image_model}"
        )

        print(
            f"[HIGGSFIELD IMAGE TOOL] Job type: "
            f"{job_type}"
        )


        # ========================================================
        # HIGGSFIELD COMMAND
        # ========================================================
        #
        # Prompt is NOT added to the Windows command line.
        #
        # This avoids:
        #
        #     The command line is too long.
        #
        # ========================================================

        command = [
            "higgsfield",
            "generate",
            "create",
            job_type,
            "--wait",
            "--json",
            "--no-color",
        ]


        # ========================================================
        # CREATE PROVIDER BRIDGE
        # ========================================================

        bridge = HiggsfieldGraphicCLI()


        # ========================================================
        # EXECUTE HIGGSFIELD
        # ========================================================

        result = bridge.execute(
            command=command,
            stdin_text=prompt,
        )


        # ========================================================
        # SAVE REMOTE IMAGE TO LOCAL ARTIFACT PATH
        # ========================================================

        output_path = None

        if result.result_url:

            try:

                print(
                    f"[HIGGSFIELD IMAGE TOOL] Downloading remote image: "
                    f"{result.result_url}"
                )

                output_path = save_remote_image_artifact(
                    job_id=job_id,
                    image_url=result.result_url,
                )

                print(
                    f"[HIGGSFIELD IMAGE TOOL] Saved local image: "
                    f"{output_path}"
                )

            except Exception as exc:

                print(
                    f"[HIGGSFIELD IMAGE TOOL] Warning downloading remote image: "
                    f"{exc}"
                )


        # ========================================================
        # RETURN TOOL RESULT
        # ========================================================

        return {
            "success": result.success,

            "provider": result.provider,

            "result_url": result.result_url,

            "output_path": output_path,

            "data": result.data,

            "job_id": job_id,

            "image_model": image_model,

            "image_job_type": job_type,
        }