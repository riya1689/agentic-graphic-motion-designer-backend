"""

Manager API Response Presenter



Purpose:

    Convert Manager internal workflow state/artifacts

    into a clean frontend-facing API response.



IMPORTANT:

    This file contains NO orchestration logic.



    It does NOT:

        - call Prompt-to-JSON Agent

        - call Planner Agent

        - call Graphic Agent

        - select tools

        - retry agents

        - generate designs



    It only converts internal backend results into

    a stable public API response.

"""



from __future__ import annotations



from typing import Any, Dict, Literal, Optional

from core.runtime_urls import public_api_url


from packages.manager_agent.api.schemas import (

    ManagerPublicResponse,

)





# ============================================================

# NORMALIZE INTERNAL MANAGER RESULT

# ============================================================



def _to_dict(

    workflow_result: Any,

) -> Dict[str, Any]:

    """

    Support both:



        - normal Python dict

        - Pydantic ManagerWorkflowState



    This keeps the presenter independent from the

    Manager state implementation.

    """



    if isinstance(

        workflow_result,

        dict,

    ):

        return workflow_result



    # Pydantic v2

    if hasattr(

        workflow_result,

        "model_dump",

    ):

        return workflow_result.model_dump()



    # Pydantic v1 compatibility

    if hasattr(

        workflow_result,

        "dict",

    ):

        return workflow_result.dict()



    raise TypeError(

        "Unsupported Manager workflow result type."

    )





# ============================================================

# GET GRAPHIC AGENT OUTPUT

# ============================================================



def _get_graphic_output(

    manager_state: Dict[str, Any],

) -> Dict[str, Any]:

    """

    Read Graphic Agent result from Manager artifacts.



    Current Manager artifact:



        artifacts[

            "graphic_phase1_receipt"

        ]



    IMPORTANT:

    Frontend does NOT know about this internal key.

    Only this presenter knows it.

    """



    artifacts = manager_state.get(

        "artifacts",

        {},

    )



    if not isinstance(

        artifacts,

        dict,

    ):

        return {}



    graphic_output = artifacts.get(

        "graphic_phase1_receipt",

        {},

    )



    if isinstance(

        graphic_output,

        dict,

    ):

        return graphic_output



    return {}





# ============================================================

# GET MOTION AGENT OUTPUT

# ============================================================



def _get_motion_output(

    manager_state: Dict[str, Any],

) -> Dict[str, Any]:

    """

    Read Motion Agent result from Manager artifacts.



    Presenter only reads stored result.

    No orchestration happens here.

    """



    artifacts = manager_state.get(

        "artifacts",

        {},

    )



    if not isinstance(

        artifacts,

        dict,

    ):

        return {}



    # Current motion result key

    motion_output = artifacts.get(

        "motion_phase1_receipt",

        {},

    )



    if isinstance(

        motion_output,

        dict,

    ):

        return motion_output



    return {}





# ============================================================

# BUILD PUBLIC RESPONSE

# ============================================================



def present_manager_response(
    workflow_result: Any,
) -> ManagerPublicResponse:

    """

    Convert complete Manager workflow result

    into frontend-facing response.



    Internal architecture:



        Manager

            ↓

        artifacts

            ↓

        Graphic Agent result

            ↓

        Presenter

            ↓

        Public API response

            ↓

        Frontend

    """



    manager_state = _to_dict(

        workflow_result

    )





    # ========================================================

    # MANAGER / WORKFLOW FAILURE

    # ========================================================



    manager_error = manager_state.get(

        "error"

    )



    manager_status = str(

        manager_state.get(

            "status",

            "",

        )

    ).lower()





    if (

        manager_error

        or manager_status == "failed"

    ):



        error_text = (

            str(manager_error)

            if manager_error

            else "Manager workflow failed."

        )



        error_lower = error_text.lower()





        # ====================================================

        # USER-FACING FAILURE NORMALIZATION

        # ====================================================



        if (

            "video generation retry limit reached"

            in error_lower

        ):



            message = (

                "Video generation retry limit reached."

            )



        elif (

            "motion generation retry limit reached"

            in error_lower

        ):



            message = (

                "Motion generation retry limit reached."

            )



        elif (

            "image generation retry limit reached"

            in error_lower

        ):



            message = (

                "Image generation retry limit reached."

            )



        else:



            message = (

                "The request could not be completed."

            )





        return ManagerPublicResponse(

            success=False,

            message=message,

            result_type=None,

            image_url=None,

            file_path=None,

            target_application=None,

            error=error_text,

        )







    # ========================================================

    # MOTION AGENT OUTPUT

    # ========================================================



    motion_output = _get_motion_output(

        manager_state

    )





    if motion_output:



        motion_status = str(

            motion_output.get(

                "status",

                "",

            )

        ).upper()





        # ====================================================

        # NORMAL VIDEO GENERATION SUCCESS

        # ====================================================



        if motion_status == "VIDEO_GENERATED":

            generated_video = motion_output.get(
                "generated_video"
            ) or motion_output.get("video_url")

            video_job_id = (
                motion_output.get("job_id")
                or manager_state.get("job_id")
            )

            video_url = None
            if (
                isinstance(generated_video, str)
                and generated_video.startswith(
                    ("http://", "https://")
                )
            ):
                video_url = generated_video
            elif video_job_id:
                video_url = public_api_url(
                    f"/api/motion/videos/{video_job_id}"
                )

            return ManagerPublicResponse(
                success=True,

                message=(
                    "Your motion video has been "
                    "generated successfully."
                ),

                result_type="video",

                image_url=video_url,

                file_path=generated_video,

                target_application=None,

                error=None,
            )





        # ====================================================

        # MOTION GENERATION FAILURE

        # ====================================================



        motion_error = motion_output.get(

            "error"

        )



        if motion_error:



            motion_error_text = str(

                motion_error

            )



            motion_error_lower = (

                motion_error_text.lower()

            )





            if (

                "video generation retry limit reached"

                in motion_error_lower

            ):



                message = (

                    "Video generation retry limit reached."

                )



            elif (

                "motion generation retry limit reached"

                in motion_error_lower

            ):



                message = (

                    "Motion generation retry limit reached."

                )



            else:



                message = (

                    "The motion request could not "

                    "be completed."

                )





            return ManagerPublicResponse(

                success=False,



                message=message,



                result_type=None,



                image_url=None,



                file_path=None,



                target_application=None,



                error=motion_error_text,

            )





        # ====================================================

        # UNKNOWN MOTION RESULT

        # ====================================================



        return ManagerPublicResponse(

            success=False,



            message=(

                "The motion agent returned an "

                "unsupported result."

            ),



            result_type=None,



            image_url=None,



            file_path=None,



            target_application=None,



            error=(

                f"Unsupported Motion Agent status: "

                f"{motion_status or 'UNKNOWN'}"

            ),

        )





    # ========================================================

    # GRAPHIC AGENT OUTPUT

    # ========================================================



    graphic_output = _get_graphic_output(

        manager_state

    )





    # --------------------------------------------------------

    # No Graphic Agent result

    # --------------------------------------------------------



    if not graphic_output:



        return ManagerPublicResponse(

            success=False,

            message=(

                "The design workflow completed without "

                "a graphic result."

            ),

            result_type=None,

            image_url=None,

            file_path=None,

            target_application=None,

            error="GRAPHIC_RESULT_MISSING",

        )





    graphic_status = str(

        graphic_output.get(

            "status",

            "",

        )

    ).upper()





    # ========================================================

    # NORMAL IMAGE GENERATION SUCCESS

    # ========================================================



    if graphic_status in {"GENERATED", "COMPLETED"}:

        generated_file = graphic_output.get(
            "generated_file"
        ) or (graphic_output.get("artifact") or {}).get("absolute_path")

        raw_result_url = (
            graphic_output.get("result_url")
            or graphic_output.get("image_url")
            or (graphic_output.get("tool_result") or {}).get("result_url")
            or generated_file
        )

        graphic_job_id = graphic_output.get("job_id") or manager_state.get("job_id")

        image_url = None
        if (
            isinstance(raw_result_url, str)
            and raw_result_url.startswith(
                ("http://", "https://")
            )
        ):
            image_url = raw_result_url
        elif graphic_job_id:
            image_url = public_api_url(
                f"/api/graphic/artifacts/{graphic_job_id}/preview"
            )

        download_url = None
        if graphic_job_id:
            download_url = public_api_url(
                f"/api/graphic/artifacts/{graphic_job_id}/download"
            )
        elif image_url:
            download_url = image_url

        artifact_format = (graphic_output.get("artifact") or {}).get("format") or "jpg"
        artifact_filename = (graphic_output.get("artifact") or {}).get("filename") or f"design_{graphic_job_id}.{artifact_format}"

        return ManagerPublicResponse(
            success=True,
            message=(
                "Your design has been generated successfully."
            ),

            result_type="image",

            job_id=graphic_job_id,

            image_url=image_url,

            download_url=download_url,

            artifact_format=artifact_format,

            artifact_filename=artifact_filename,

            file_path=str(generated_file) if generated_file else None,

            target_application=None,

            error=None,

        )





    # ========================================================

    # JSX FALLBACK SUCCESS

    # ========================================================



    if graphic_status == "FALLBACK_GENERATED":



        fallback_file = graphic_output.get(

            "fallback_file"

        )



        fallback_tool = str(

            graphic_output.get(

                "fallback_tool",

                "",

            )

        ).lower()





        # ----------------------------------------------------

        # Presentation mapping only.

        #

        # This does NOT select which tool to execute.

        # Graphic Agent already made that decision.

        # ----------------------------------------------------



        target_application = None



        if fallback_tool == "illustrator_jsx":



            target_application = (

                "adobe_illustrator"

            )



        elif fallback_tool == "photoshop_jsx":



            target_application = (

                "adobe_photoshop"

            )





        # ----------------------------------------------------

        # User-facing message

        # ----------------------------------------------------



        if (

            target_application

            == "adobe_illustrator"

        ):



            message = (

                "Image generated successfully. "

                "Open the generated JSX file with "

                "Adobe Illustrator."

            )



        elif (

            target_application

            == "adobe_photoshop"

        ):



            message = (

                "Image generated successfully. "

                "Open the generated JSX file with "

                "Adobe Photoshop."

            )



        else:



            message = (

                "Image generation was unavailable, "

                "but a JSX fallback script was "

                "generated successfully."

            )





        return ManagerPublicResponse(

            success=True,



            message=message,



            result_type="jsx_fallback",



            image_url=None,



            file_path=fallback_file,



            target_application=target_application,



            error=None,

        )





    # ========================================================

    # UNKNOWN GRAPHIC RESULT

    # ========================================================



    return ManagerPublicResponse(

        success=False,



        message=(

            "The graphic agent returned an unsupported result."

        ),



        result_type=None,



        image_url=None,



        file_path=None,



        target_application=None,



        error=(

            f"Unsupported Graphic Agent status: "

            f"{graphic_status or 'UNKNOWN'}"

        ),

    )



# """
# Manager API Response Presenter

# Purpose:
#     Convert Manager internal workflow state/artifacts
#     into a clean frontend-facing API response.

# IMPORTANT:
#     This file contains NO orchestration logic.

#     It does NOT:
#         - call Prompt-to-JSON Agent
#         - call Planner Agent
#         - call Graphic Agent
#         - select tools
#         - retry agents
#         - generate designs

#     It only converts internal backend results into
#     a stable public API response.
# """

# from __future__ import annotations

# from typing import Any, Dict, Literal, Optional

# from packages.manager_agent.api.schemas import (
#     ManagerPublicResponse,
# )


# # ============================================================
# # NORMALIZE INTERNAL MANAGER RESULT
# # ============================================================

# def _to_dict(
#     workflow_result: Any,
# ) -> Dict[str, Any]:
#     """
#     Support both:

#         - normal Python dict
#         - Pydantic ManagerWorkflowState

#     This keeps the presenter independent from the
#     Manager state implementation.
#     """

#     if isinstance(
#         workflow_result,
#         dict,
#     ):
#         return workflow_result

#     # Pydantic v2
#     if hasattr(
#         workflow_result,
#         "model_dump",
#     ):
#         return workflow_result.model_dump()

#     # Pydantic v1 compatibility
#     if hasattr(
#         workflow_result,
#         "dict",
#     ):
#         return workflow_result.dict()

#     raise TypeError(
#         "Unsupported Manager workflow result type."
#     )


# # ============================================================
# # GET GRAPHIC AGENT OUTPUT
# # ============================================================

# def _get_graphic_output(
#     manager_state: Dict[str, Any],
# ) -> Dict[str, Any]:
#     """
#     Read Graphic Agent result from Manager artifacts.

#     Current Manager artifact:

#         artifacts[
#             "graphic_phase1_receipt"
#         ]

#     IMPORTANT:
#     Frontend does NOT know about this internal key.
#     Only this presenter knows it.
#     """

#     artifacts = manager_state.get(
#         "artifacts",
#         {},
#     )

#     if not isinstance(
#         artifacts,
#         dict,
#     ):
#         return {}

#     graphic_output = artifacts.get(
#         "graphic_phase1_receipt",
#         {},
#     )

#     if isinstance(
#         graphic_output,
#         dict,
#     ):
#         return graphic_output

#     return {}


# # ============================================================
# # GET MOTION AGENT OUTPUT
# # ============================================================

# def _get_motion_output(
#     manager_state: Dict[str, Any],
# ) -> Dict[str, Any]:
#     """
#     Read Motion Agent result from Manager artifacts.

#     Presenter only reads stored result.
#     No orchestration happens here.
#     """

#     artifacts = manager_state.get(
#         "artifacts",
#         {},
#     )

#     if not isinstance(
#         artifacts,
#         dict,
#     ):
#         return {}

#     # Current motion result key
#     motion_output = artifacts.get(
#         "motion_phase1_receipt",
#         {},
#     )

#     if isinstance(
#         motion_output,
#         dict,
#     ):
#         return motion_output

#     return {}


# # ============================================================
# # BUILD PUBLIC RESPONSE
# # ============================================================

# def present_manager_response(
#     state,
#     workflow_result: Any,
# ) -> ManagerPublicResponse:
#     """
#     Convert complete Manager workflow result
#     into frontend-facing response.

#     Internal architecture:

#         Manager
#             ↓
#         artifacts
#             ↓
#         Graphic Agent result
#             ↓
#         Presenter
#             ↓
#         Public API response
#             ↓
#         Frontend
#     """

#     manager_state = _to_dict(
#         workflow_result
#     )


#     # ========================================================
#     # MANAGER / WORKFLOW FAILURE
#     # ========================================================

#     manager_error = manager_state.get(
#         "error"
#     )

#     manager_status = str(
#         manager_state.get(
#             "status",
#             "",
#         )
#     ).lower()


#     if (
#         manager_error
#         or manager_status == "failed"
#     ):

#         error_text = (
#             str(manager_error)
#             if manager_error
#             else "Manager workflow failed."
#         )

#         error_lower = error_text.lower()


#         # ====================================================
#         # USER-FACING FAILURE NORMALIZATION
#         # ====================================================

#         if (
#             "video generation retry limit reached"
#             in error_lower
#         ):

#             message = (
#                 "Video generation retry limit reached."
#             )

#         elif (
#             "motion generation retry limit reached"
#             in error_lower
#         ):

#             message = (
#                 "Motion generation retry limit reached."
#             )

#         elif (
#             "image generation retry limit reached"
#             in error_lower
#         ):

#             message = (
#                 "Image generation retry limit reached."
#             )

#         else:

#             message = (
#                 "The request could not be completed."
#             )


#         return ManagerPublicResponse(
#             success=False,
#             message=message,
#             result_type=None,
#             image_url=None,
#             file_path=None,
#             target_application=None,
#             error=error_text,
#         )



#     # ========================================================
#     # MOTION AGENT OUTPUT
#     # ========================================================

#     motion_output = _get_motion_output(
#         manager_state
#     )


#     if motion_output:

#         motion_status = str(
#             motion_output.get(
#                 "status",
#                 "",
#             )
#         ).upper()


#         # ====================================================
#         # NORMAL VIDEO GENERATION SUCCESS
#         # ====================================================

#         if motion_status == "VIDEO_GENERATED":

#             generated_video = motion_output.get(
#                 "generated_video"
#             )


#             return ManagerPublicResponse(
#                 success=True,

#                 message=(
#                     "Your motion video has been "
#                     "generated successfully."
#                 ),

#                 result_type="video",

#                 image_url=None,

#                 file_path=generated_video,

#                 target_application=None,

#                 error=None,
#             )


#         # ====================================================
#         # MOTION GENERATION FAILURE
#         # ====================================================

#         motion_error = motion_output.get(
#             "error"
#         )

#         if motion_error:

#             motion_error_text = str(
#                 motion_error
#             )

#             motion_error_lower = (
#                 motion_error_text.lower()
#             )


#             if (
#                 "video generation retry limit reached"
#                 in motion_error_lower
#             ):

#                 message = (
#                     "Video generation retry limit reached."
#                 )

#             elif (
#                 "motion generation retry limit reached"
#                 in motion_error_lower
#             ):

#                 message = (
#                     "Motion generation retry limit reached."
#                 )

#             else:

#                 message = (
#                     "The motion request could not "
#                     "be completed."
#                 )


#             return ManagerPublicResponse(
#                 success=False,

#                 message=message,

#                 result_type=None,

#                 image_url=None,

#                 file_path=None,

#                 target_application=None,

#                 error=motion_error_text,
#             )


#         # ====================================================
#         # UNKNOWN MOTION RESULT
#         # ====================================================

#         return ManagerPublicResponse(
#             success=False,

#             message=(
#                 "The motion agent returned an "
#                 "unsupported result."
#             ),

#             result_type=None,

#             image_url=None,

#             file_path=None,

#             target_application=None,

#             error=(
#                 f"Unsupported Motion Agent status: "
#                 f"{motion_status or 'UNKNOWN'}"
#             ),
#         )


#     # ========================================================
#     # GRAPHIC AGENT OUTPUT
#     # ========================================================

#     graphic_output = _get_graphic_output(
#         manager_state
#     )


#     # --------------------------------------------------------
#     # No Graphic Agent result
#     # --------------------------------------------------------

#     if not graphic_output:

#         return ManagerPublicResponse(
#             success=False,
#             message=(
#                 "The design workflow completed without "
#                 "a graphic result."
#             ),
#             result_type=None,
#             image_url=None,
#             file_path=None,
#             target_application=None,
#             error="GRAPHIC_RESULT_MISSING",
#         )


#     graphic_status = str(
#         graphic_output.get(
#             "status",
#             "",
#         )
#     ).upper()


#     # ========================================================
#     # NORMAL IMAGE GENERATION SUCCESS
#     # ========================================================

#     if graphic_status == "GENERATED":

#         generated_file = graphic_output.get(
#             "generated_file"
#         )

#         return ManagerPublicResponse(
#             success=True,
#             message=(
#                 "Your design has been generated successfully."
#             ),

#             result_type="image",

#             # IMPORTANT:
#             #
#             # Do NOT expose local Windows filesystem path as
#             # image_url.
#             #
#             # Browser cannot display:
#             #
#             # D:\\project\\runtime-data\\...\\generated.jpg
#             #
#             # image_url will be added when backend exposes
#             # generated files through a public/static endpoint.
#             image_url=None,

#             file_path=generated_file,

#             target_application=None,

#             error=None,
#         )


#     # ========================================================
#     # JSX FALLBACK SUCCESS
#     # ========================================================

#     if graphic_status == "FALLBACK_GENERATED":

#         fallback_file = graphic_output.get(
#             "fallback_file"
#         )

#         fallback_tool = str(
#             graphic_output.get(
#                 "fallback_tool",
#                 "",
#             )
#         ).lower()


#         # ----------------------------------------------------
#         # Presentation mapping only.
#         #
#         # This does NOT select which tool to execute.
#         # Graphic Agent already made that decision.
#         # ----------------------------------------------------

#         target_application = None

#         if fallback_tool == "illustrator_jsx":

#             target_application = (
#                 "adobe_illustrator"
#             )

#         elif fallback_tool == "photoshop_jsx":

#             target_application = (
#                 "adobe_photoshop"
#             )


#         # ----------------------------------------------------
#         # User-facing message
#         # ----------------------------------------------------

#         if (
#             target_application
#             == "adobe_illustrator"
#         ):

#             message = (
#                 "Image generated successfully. "
#                 "Open the generated JSX file with "
#                 "Adobe Illustrator."
#             )

#         elif (
#             target_application
#             == "adobe_photoshop"
#         ):

#             message = (
#                 "Image generated successfully. "
#                 "Open the generated JSX file with "
#                 "Adobe Photoshop."
#             )

#         else:

#             message = (
#                 "Image generation was unavailable, "
#                 "but a JSX fallback script was "
#                 "generated successfully."
#             )


#         return ManagerPublicResponse(
#             success=True,

#             message=message,

#             result_type="jsx_fallback",

#             image_url=None,

#             file_path=fallback_file,

#             target_application=target_application,

#             error=None,
#         )


#     # ========================================================
#     # UNKNOWN GRAPHIC RESULT
#     # ========================================================

#     return ManagerPublicResponse(
#         success=False,

#         message=(
#             "The graphic agent returned an unsupported result."
#         ),

#         result_type=None,

#         image_url=None,

#         file_path=None,

#         target_application=None,

#         error=(
#             f"Unsupported Graphic Agent status: "
#             f"{graphic_status or 'UNKNOWN'}"
#         ),
#     )
