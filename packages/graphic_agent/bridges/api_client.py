"""
Graphic Agent Direct API Bridge

Purpose:
    External cloud APIs-এর সাথে communication isolate করা।

Phase-2:
    Gemini / Nano Banana image generation.

Future:
    Canva API
    other image APIs
"""

from __future__ import annotations

import base64
import os

from pathlib import Path
from typing import Dict, Any

from google import genai
from google.genai import errors

from packages.graphic_agent.bridges.key_pool import (
    load_graphic_gemini_api_keys,
)


# ============================================================
# GEMINI IMAGE API CLIENT
# ============================================================

class GeminiImageAPIClient:

    def __init__(self):

        # ----------------------------------------------------
        # Load API keys in priority order
        # ----------------------------------------------------

        self.api_keys = (
            load_graphic_gemini_api_keys()
        )

        self.model = os.getenv(
            "GRAPHIC_GEMINI_IMAGE_MODEL",
            "gemini-3.5-flash-lite",
        )


    # ========================================================
    # GENERATE IMAGE
    # ========================================================

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
    ) -> Dict[str, Any]:

        last_error = None

        total_keys = len(
            self.api_keys
        )

        # ====================================================
        # KEY FAILOVER LOOP
        # ====================================================

        for index, api_key in enumerate(
            self.api_keys,
            start=1,
        ):

            print(
                "[API BRIDGE] Trying Gemini credential "
                f"{index}/{total_keys}"
            )

            try:

                # --------------------------------------------
                # Create client for current credential
                # --------------------------------------------

                client = genai.Client(
                    api_key=api_key
                )


                # --------------------------------------------
                # Generate image
                # --------------------------------------------

                interaction = (
                    client.interactions.create(

                        model=self.model,

                        input=prompt,

                        response_format={
                            "type": "image",
                            "mime_type": "image/jpeg",
                        },
                    )
                )


                # --------------------------------------------
                # Read generated image
                # --------------------------------------------

                generated_image = (
                    interaction.output_image
                )

                if generated_image is None:

                    raise RuntimeError(
                        "Gemini returned no image."
                    )


                # --------------------------------------------
                # Decode image
                # --------------------------------------------

                image_bytes = base64.b64decode(
                    generated_image.data
                )


                # --------------------------------------------
                # Save image
                # --------------------------------------------

                output_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                output_path.write_bytes(
                    image_bytes
                )


                print(
                    "[API BRIDGE] Gemini credential "
                    f"{index} succeeded"
                )


                return {
                    "success": True,
                    "model": self.model,
                    "credential_index": index,
                    "output_path": str(output_path),
                    "bytes_written": len(image_bytes),
                }


            # =================================================
            # GEMINI API ERROR
            # =================================================

            except errors.APIError as exc:

                last_error = exc

                error_code = getattr(
                    exc,
                    "code",
                    None,
                )

                print(
                    "[API BRIDGE] Gemini credential "
                    f"{index} failed with HTTP {error_code}"
                )


                # ---------------------------------------------
                # 429 = quota / rate limit
                #
                # Try next configured credential.
                # ---------------------------------------------

                if error_code == 429:

                    if index < total_keys:

                        print(
                            "[API BRIDGE] Trying next "
                            "configured credential..."
                        )

                        continue

                    break


                # ---------------------------------------------
                # Other errors:
                #
                # Don't blindly rotate keys for bad requests,
                # unsupported parameters, etc.
                # ---------------------------------------------

                raise


            # =================================================
            # OTHER ERROR
            # =================================================

            except Exception as exc:

                last_error = exc

                raise


        # ====================================================
        # ALL CONFIGURED KEYS EXHAUSTED
        # ====================================================

        raise RuntimeError(
            "All configured Graphic Gemini API credentials "
            f"were unavailable. Last error: {last_error}"
        )



# """
# Graphic Agent Direct API Bridge

# Purpose:
#     External cloud APIs-এর সাথে communication isolate করা।

# Phase-2:
#     Gemini / Nano Banana image generation.

# Future:
#     Canva API
#     other image APIs
# """

# from __future__ import annotations

# import base64
# import os
# from pathlib import Path
# from typing import Dict, Any

# from google.genai import errors

# from packages.graphic_agent.bridges.key_pool import (
#     load_graphic_gemini_api_keys,
# )


# # ============================================================
# # GEMINI IMAGE API CLIENT
# # ============================================================

# class GeminiImageAPIClient:

#     def __init__(self):

#         # ----------------------------------------------------
#         # Load API keys in priority order
#         # ----------------------------------------------------

#         self.api_keys = (
#             load_graphic_gemini_api_keys()
#         )

#         self.model = os.getenv(
#             "GRAPHIC_GEMINI_IMAGE_MODEL",
#             "gemini-3.5-flash-lite",
#         )


#     # ========================================================
#     # GENERATE IMAGE
#     # ========================================================

#     def generate_image(
#         self,
#         prompt: str,
#         output_path: Path,
#     ) -> Dict[str, Any]:

#         interaction = (
#             self.client.interactions.create(
#                 model=self.model,
#                 input=prompt,
#                 response_format={
#                     "type": "image",
#                     "mime_type": "image/jpeg",
#                 },
#             )
#         )

#         generated_image = (
#             interaction.output_image
#         )

#         if generated_image is None:

#             raise RuntimeError(
#                 "Gemini returned no image."
#             )

#         image_bytes = base64.b64decode(
#             generated_image.data
#         )

#         output_path.parent.mkdir(
#             parents=True,
#             exist_ok=True,
#         )

#         output_path.write_bytes(
#             image_bytes
#         )

#         return {
#             "success": True,
#             "model": self.model,
#             "output_path": str(output_path),
#             "bytes_written": len(image_bytes),
#         }