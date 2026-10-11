"""
Standalone Motion Agent Phase-1 Test

This test does NOT require:

- Manager
- Gemini
- Wan
- LTX
- FFmpeg

It only tests the Motion Agent workflow contract.
"""

from packages.motion_agent.agent.graph import (
    run_motion_workflow,
)

from packages.motion_agent.domain.schema import (
    MotionTask,
)


# ============================================================
# TEST PLANNER PLAN
# ============================================================

planner_plan = {

    "planner_status":
        "completed",

    "job_summary":
        "Create a short motion video.",

    "primary_job_type":
        "motion_design",

    "target_software":
        "video_generation",

    "previous_asset_required":
        False,

    "asset_requests":
        [],

    "tasks": [

        {
            "task_id":
                "task_1",

            "title":
                "Create motion scene",

            "description":
                "Generate the requested motion content.",

            "job_type":
                "motion_design",

            "required_capabilities":
                [
                    "video_generation"
                ],

            "depends_on":
                [],

            "can_run_parallel":
                False,

            "inputs":
                [],

            "expected_outputs":
                [
                    "motion_video"
                ],

            "constraints":
                [],

            "acceptance_criteria":
                [
                    "Video matches requested motion."
                ],

        }

    ],

    "execution_order":
        [
            "task_1"
        ],

    "global_constraints":
        [],

    "final_deliverables":
        [
            "motion_video"
        ],

    "verification": {

        "required":
            True,

        "checks":
            [
                "motion requirement coverage"
            ],

        "retry_on_failure":
            True,

        "max_repair_attempts":
            2,

    },

}


# ============================================================
# CREATE TASK
# ============================================================

task = MotionTask(

    job_id=
        "motion-phase1-test",

    planner_plan=
        planner_plan,

    original_user_request=
        "Create a short cinematic motion video.",

    max_validation_attempts=
        2,

)


# ============================================================
# RUN
# ============================================================

state = run_motion_workflow(
    task
)


# ============================================================
# RESULT
# ============================================================

print()

print("=" * 70)

print("FINAL MOTION AGENT STATE")

print("=" * 70)

print(
    state.model_dump_json(
        indent=2
    )
)