"""

Manager Agent Workflow



PHASE 1 FLOW:



User Prompt



    ↓



Manager



    ↓



Create Job



    ↓



Prompt-to-JSON Agent



    ↓



Receive JSON



    ↓



Track Completed



    ↓



Set Planner as Next Agent



IMPORTANT:



এই Phase-এ Planner execute হবে না।



"""



from __future__ import annotations



import uuid



from typing import Dict



import json



from packages.manager_agent.orchestrator.dispatcher import (

    dispatch_to_agent,

)



from packages.manager_agent.orchestrator.state import (

    AgentTaskStatus,

    ManagerWorkflowState,

    WorkflowStatus,

)



# ============================================================

# ADDED: DETERMINISTIC SPECIALIZED-AGENT ROUTING

# ============================================================



def select_execution_agent(

    planner_output: dict,

) -> str:

    """

    Select specialized execution agent from Planner output.



    IMPORTANT:



    This function does NOT:

    - plan

    - design

    - generate motion

    - choose Wan/LTX

    - choose Illustrator/Photoshop tools



    It only performs deterministic orchestration routing.

    """



    primary_job_type = planner_output.get(

        "primary_job_type"

    )



    if primary_job_type == "graphic_design":



        return "graphic_agent"



    if primary_job_type == "motion_design":



        return "motion_agent"



    raise ValueError(

        "Manager cannot route Planner output. "

        f"Unsupported primary_job_type: "

        f"{primary_job_type!r}"

    )





# ============================================================

# TEMPORARY IN-MEMORY JOB STORE

# ============================================================



# Phase-1 testing-এর জন্য memory store ব্যবহার করছি।

#

# পরে এটি replace করা যাবে:

# - PostgreSQL

# - Redis

# - Durable workflow store

#

# কিন্তু এখন architecture test করার জন্য যথেষ্ট।



JOB_STORE: Dict[str, ManagerWorkflowState] = {}





# ============================================================

# CREATE NEW JOB

# ============================================================



def create_job(user_prompt: str,

    selected_image_model: str | None = None,

    selected_video_model: str | None = None,

) -> ManagerWorkflowState:

    """

    User prompt থেকে নতুন Manager workflow তৈরি করে।

    """



    job_id = str(uuid.uuid4())



    state = ManagerWorkflowState(

        job_id=job_id,

        original_prompt=user_prompt,

        selected_image_model=selected_image_model,

        selected_video_model=selected_video_model,

        status=WorkflowStatus.CREATED,

        current_stage="manager_received",

        current_agent=None,

        next_agent="prompt_to_json_agent",

    )



    # Job store করো

    JOB_STORE[job_id] = state



    return state





# ============================================================

# SAVE / UPDATE JOB

# ============================================================



def save_job(state: ManagerWorkflowState) -> None:

    """

    Updated state memory-তে save করে।

    """



    JOB_STORE[state.job_id] = state





# ============================================================

# GET JOB

# ============================================================



def get_job(job_id: str) -> ManagerWorkflowState:

    """

    Job ID দিয়ে workflow state return করে।

    """



    state = JOB_STORE.get(job_id)



    if not state:

        raise ValueError(

            f"Job '{job_id}' not found."

        )



    return state





# ============================================================

# GENERIC AGENT FAILURE TRACKER

# ============================================================

#

# ADDED:

#

# Previously the single except block always marked

# prompt_to_json_agent as failed.

#

# That becomes incorrect once Planner Agent exists.

#

# This helper allows Manager to fail the CURRENT agent

# without mixing agent-specific business logic.

# ============================================================



def mark_agent_failed(

    state: ManagerWorkflowState,

    agent_id: str,

    stage: str,

    error: Exception | str,

) -> ManagerWorkflowState:

    """

    Mark one agent execution as failed.



    This is orchestration/state-management logic only.

    """



    error_message = str(error)



    state.status = WorkflowStatus.FAILED



    state.current_stage = stage



    state.current_agent = agent_id



    state.next_agent = None



    # Only update the requested agent.

    if agent_id in state.agent_tasks:



        state.agent_tasks[

            agent_id

        ].status = AgentTaskStatus.FAILED



        state.agent_tasks[

            agent_id

        ].error = error_message



    save_job(state)



    print(

        f"[MANAGER] {agent_id} status = FAILED"

    )



    print(

        f"[MANAGER] Error: {error_message}"

    )



    return state





# ============================================================

# MANAGER PHASE-1 WORKFLOW

# ============================================================



async def run_manager_workflow(

    user_prompt: str,

    selected_image_model: str | None = None,

    selected_video_model: str | None = None,

) -> ManagerWorkflowState:

    print("\n" + "=" * 70)

    print("[MANAGER] Received user prompt")

    print(f"[MANAGER] Prompt: {user_prompt}")

    print("=" * 70)

    # ========================================================

    # STEP 1 — CREATE JOB

    # ========================================================

    state = create_job(

        user_prompt,

        selected_image_model=selected_image_model,

        selected_video_model=selected_video_model,

    )



    print(f"[MANAGER] Job created: {state.job_id}")



    state.status = WorkflowStatus.RUNNING



    state.current_stage = "prompt_to_json"



    state.current_agent = "prompt_to_json_agent"



    state.next_agent = None



    state.agent_tasks[

        "prompt_to_json_agent"

    ].status = AgentTaskStatus.RUNNING



    save_job(state)



    print("[MANAGER] prompt_to_json_agent status = RUNNING")



    # ========================================================

    # STEP 2 — PREPARE PAYLOAD

    # ========================================================



    prompt_agent_payload = {

        "job_id": state.job_id,

        "prompt": state.original_prompt,

    }



    print("[MANAGER] Sending prompt to prompt_to_json_agent...")



    # ========================================================

    # STEP 3 — SEND TASK TO PROMPT-TO-JSON AGENT

    # ========================================================



    try:



        response = await dispatch_to_agent(

            agent_id="prompt_to_json_agent",

            payload=prompt_agent_payload,

        )



        print("[MANAGER] Response received from prompt_to_json_agent")



        print("\n[MANAGER] JSON Agent returned this output:")



        print(

            json.dumps(

                response,

                indent=2,

                ensure_ascii=False,

            )

        )



        print()



        # ====================================================

        # STEP 4 — VALIDATE BASIC AGENT RESPONSE

        # ====================================================



        if not response.get("success"):



            raise RuntimeError(

                response.get(

                    "error",

                    "Prompt-to-JSON Agent returned unsuccessful response."

                )

            )



        # ====================================================

        # STEP 5 — STORE AGENT OUTPUT

        # ====================================================



        prompt_json_output = response.get("output")



        print("[MANAGER] JSON output received successfully")



        state.artifacts[

            "prompt_json"

        ] = prompt_json_output



        # ====================================================

        # STEP 6 — MARK JSON AGENT COMPLETED

        # ====================================================



        state.agent_tasks[

            "prompt_to_json_agent"

        ].status = AgentTaskStatus.COMPLETED



        state.agent_tasks[

            "prompt_to_json_agent"

        ].output = prompt_json_output



        print(

            "[MANAGER] prompt_to_json_agent status = COMPLETED"

        )



        # ====================================================

        # STEP 7 — MOVE WORKFLOW TO NEXT STAGE

        # ====================================================



        state.current_agent = None



        state.current_stage = "prompt_to_json_completed"



        # Planner execution এখনো করবো না।

        # শুধু Manager জানবে next step কী।



        state.next_agent = "planner_agent"



        save_job(state)



        print("[MANAGER] Workflow state saved")



        print("[MANAGER] Next agent = planner_agent")



    # ========================================================

    # ERROR HANDLING

    # ========================================================



    except Exception as exc:



        print(f"[MANAGER] ERROR: {exc}")



        state.status = WorkflowStatus.FAILED



        state.current_stage = "prompt_to_json_failed"



        state.agent_tasks[

            "prompt_to_json_agent"

        ].status = AgentTaskStatus.FAILED



        state.agent_tasks[

            "prompt_to_json_agent"

        ].error = str(exc)



        save_job(state)



        print(

            "[MANAGER] prompt_to_json_agent status = FAILED"

        )



        return state





    # ========================================================

    # ADDED — PLANNER AGENT EXECUTION

    # ========================================================

    #

    # IMPORTANT:

    #

    # JSON Agent-এর existing logic এখানে change করা হয়নি।

    #

    # এখন JSON Agent successfully complete হওয়ার পরে

    # Manager Planner Agent-কে task assign করবে।

    #

    # Manager Planner-এর internal planning logic জানবে না।

    #

    # Planner-এর:

    #

    # - planning

    # - validation

    # - verification

    # - repair

    # - hill-climbing

    #

    # সব Planner Agent-এর নিজের graph-এর ভিতরে হবে।

    #

    # Manager শুধু:

    #

    # assign

    # track

    # receive

    # store

    #

    # করবে।

    # ========================================================





    # ========================================================

    # STEP 8 — MARK PLANNER AGENT RUNNING

    # ========================================================



    state.current_stage = "planner"



    state.current_agent = "planner_agent"



    state.next_agent = None



    state.agent_tasks[

        "planner_agent"

    ].status = AgentTaskStatus.RUNNING



    save_job(state)



    print()



    print("-" * 70)



    print(

        "[MANAGER] Assigning task to planner_agent"

    )



    print(

        "[MANAGER] planner_agent status = RUNNING"

    )





    # ========================================================

    # STEP 9 — PREPARE PLANNER PAYLOAD

    # ========================================================

    #

    # ADDED:

    #

    # Planner Agent-এর API contract অনুযায়ী

    # Manager নিচের data পাঠাবে:

    #

    # - same job_id

    # - JSON Agent output

    # - original user request

    # - maximum repair attempts

    #

    # Manager এখানে planning করছে না।

    # ========================================================



    planner_payload = {



        "job_id": state.job_id,



        "json_agent_output": prompt_json_output,



        "original_user_request": state.original_prompt,



        # Planner-এর verification / hill-climbing loop

        # bounded রাখার জন্য maximum repair limit।

        "max_repair_attempts": 3,

    }



    print(

        "[MANAGER] Sending JSON requirements to planner_agent..."

    )





    # ========================================================

    # STEP 10 — SEND TASK TO PLANNER AGENT

    # ========================================================



    try:



        planner_response = await dispatch_to_agent(

            agent_id="planner_agent",

            payload=planner_payload,

        )



    except Exception as exc:



        # ====================================================

        # ADDED:

        # Planner failure হলে JSON Agent-কে FAILED করা হবে না।

        #

        # যে agent fail করেছে শুধু তাকেই FAILED করা হবে।

        # ====================================================



        return mark_agent_failed(

            state=state,

            agent_id="planner_agent",

            stage="planner_failed",

            error=exc,

        )





    # ========================================================

    # STEP 11 — RECEIVE PLANNER RESPONSE

    # ========================================================



    print(

        "[MANAGER] Response received from planner_agent"

    )



    print()



    print(

        "[MANAGER] Planner Agent returned this output:"

    )



    # ========================================================

    # ADDED:

    #

    # Planner Agent Manager-কে যে complete JSON return করেছে

    # সেটা terminal-এ print হবে।

    #

    # এতে আমরা confirm করতে পারবো:

    #

    # - Planner কাজ receive করেছে

    # - planning complete হয়েছে

    # - loop run হয়েছে কি না

    # - verification score

    # - final plan

    # ========================================================



    print(

        json.dumps(

            planner_response,

            indent=2,

            ensure_ascii=False,

        )

    )



    print()





    # ========================================================

    # STEP 12 — VALIDATE BASIC PLANNER RESPONSE

    # ========================================================

    #

    # IMPORTANT:

    #

    # Manager Planner-এর plan আবার verify করবে না।

    #

    # Planner Agent already internally করেছে:

    #

    # planning

    #     ↓

    # validation

    #     ↓

    # verification

    #     ↓

    # repair / hill-climbing if needed

    #     ↓

    # finalization

    #

    # Manager শুধু success / failure check করছে।

    # ========================================================



    if not planner_response.get("success"):



        return mark_agent_failed(

            state=state,

            agent_id="planner_agent",

            stage="planner_failed",

            error=planner_response.get(

                "error",

                "Planner Agent returned unsuccessful response."

            ),

        )





    # ========================================================

    # STEP 13 — GET FINAL PLANNER OUTPUT

    # ========================================================



    planner_output = planner_response.get(

        "final_output"

    )



    # ========================================================

    # ADDED:

    #

    # Planner success বলেছে কিন্তু final plan না থাকলে

    # সেটা valid completion না।

    # ========================================================



    if planner_output is None:



        return mark_agent_failed(

            state=state,

            agent_id="planner_agent",

            stage="planner_failed",

            error=(

                "Planner Agent returned success "

                "but final_output is missing."

            ),

        )





    # ========================================================

    # STEP 14 — STORE PLANNER OUTPUT

    # ========================================================



    state.artifacts[

        "planner_plan"

    ] = planner_output





    # ========================================================

    # ADDED — STORE PLANNER EXECUTION METADATA

    # ========================================================

    #

    # Planner-এর actual plan থেকে runtime metadata আলাদা

    # রাখা হচ্ছে।

    #

    # এতে business output clean থাকবে।

    #

    # Future observability/debugging সহজ হবে।

    # ========================================================



    state.artifacts[

        "planner_metadata"

    ] = {



        "planning_iteration": planner_response.get(

            "planning_iteration",

            0,

        ),



        "repair_attempt": planner_response.get(

            "repair_attempt",

            0,

        ),



        "verification_score": planner_response.get(

            "verification_score",

            0.0,

        ),



        "best_score": planner_response.get(

            "best_score",

            0.0,

        ),

    }





    # ========================================================

    # STEP 15 — MARK PLANNER AGENT COMPLETED

    # ========================================================



    state.agent_tasks[

        "planner_agent"

    ].status = AgentTaskStatus.COMPLETED



    state.agent_tasks[

        "planner_agent"

    ].output = planner_output



    state.agent_tasks[

        "planner_agent"

    ].error = None



    print(

        "[MANAGER] planner_agent status = COMPLETED"

    )





    # ========================================================

    # STEP 16 — MOVE WORKFLOW TO NEXT STAGE

    # ========================================================

    #

    # ADDED:

    #

    # Planner complete হওয়ার পরে Manager শুধু জানবে

    # next job কোন agent-এর।

    #

    # Graphic Agent এখন execute করা হচ্ছে না।

    #

    # Graphic Agent implementation future step।

    # ========================================================



    # ========================================================

    # CHANGED — ROUTE PLANNER OUTPUT TO SPECIALIZED AGENT

    # ========================================================

    #

    # Previously:

    #

    #     Planner

    #        ↓

    #     graphic_agent

    #

    # was hardcoded.

    #

    # Now:

    #

    #     primary_job_type = graphic_design

    #                ↓

    #          graphic_agent

    #

    #     primary_job_type = motion_design

    #                ↓

    #           motion_agent

    #

    # Manager still performs orchestration only.

    # ========================================================



    try:



        execution_agent = select_execution_agent(

            planner_output

        )



    except Exception as exc:



        state.status = WorkflowStatus.FAILED



        state.current_stage = (

            "execution_agent_routing_failed"

        )



        state.current_agent = None



        state.next_agent = None



        save_job(state)



        print(

            "[MANAGER] Execution-agent routing = FAILED"

        )



        print(

            f"[MANAGER] Error: {exc}"

        )



        return state





    # ========================================================

    # ROUTING SUCCESS

    # ========================================================



    state.current_agent = None



    state.current_stage = "planner_completed"



    state.next_agent = execution_agent



    state.status = WorkflowStatus.RUNNING



    save_job(state)





    print(

        "[MANAGER] Planner output stored"

    )



    print(

        "[MANAGER] Workflow state saved"

    )



    print(

        f"[MANAGER] Next agent = {execution_agent}"

    )





    # ========================================================

    # ADDED — MOTION AGENT EXECUTION BRANCH

    # ========================================================

    #

    # IMPORTANT:

    #

    # If Planner classified the job as:

    #

    #     primary_job_type = motion_design

    #

    # Manager dispatches the same verified Planner output

    # directly to Motion Agent.

    #

    # Manager does NOT:

    #

    # - modify the motion plan

    # - create video prompts

    # - select Wan

    # - select LTX

    # - run FFmpeg

    #

    # Existing Graphic Agent path below remains unchanged.

    # ========================================================



    if execution_agent == "motion_agent":





        # ====================================================

        # MOTION STEP 1 — MARK MOTION AGENT RUNNING

        # ====================================================



        state.current_stage = "motion_agent"



        state.current_agent = "motion_agent"



        state.next_agent = None





        state.agent_tasks[

            "motion_agent"

        ].status = AgentTaskStatus.RUNNING





        save_job(state)





        print()



        print("-" * 70)



        print(

            "[MANAGER] Assigning Planner plan to motion_agent"

        )



        print(

            "[MANAGER] motion_agent status = RUNNING"

        )





        # ====================================================

        # MOTION STEP 2 — PREPARE MOTION PAYLOAD

        # ====================================================



        motion_payload = {



            "job_id":

                state.job_id,



            "planner_plan":

                planner_output,



            "original_user_request":

                state.original_prompt,



            "max_validation_attempts":

                2,



        }





        print(

            "[MANAGER] Sending Planner plan to motion_agent..."

        )





        # ====================================================

        # MOTION STEP 3 — DISPATCH TO MOTION AGENT

        # ====================================================



        try:



            motion_response = await dispatch_to_agent(



                agent_id="motion_agent",



                payload=motion_payload,



            )



        except Exception as exc:



            return mark_agent_failed(



                state=state,



                agent_id="motion_agent",



                stage="motion_agent_failed",



                error=exc,



            )





        # ====================================================

        # MOTION STEP 4 — RECEIVE RESPONSE

        # ====================================================



        print(

            "[MANAGER] Response received from motion_agent"

        )



        print()



        print(

            "[MANAGER] Motion Agent returned this output:"

        )



        print(

            json.dumps(

                motion_response,

                indent=2,

                ensure_ascii=False,

            )

        )



        print()





        # ====================================================

        # MOTION STEP 5 — BASIC RESPONSE VALIDATION

        # ====================================================

        #

        # Manager Motion Agent-এর internal validation

        # repeat করবে না।

        #

        # Manager শুধু service-level success check করবে।

        # ====================================================



        if not motion_response.get(

            "success"

        ):



            return mark_agent_failed(



                state=state,



                agent_id="motion_agent",



                stage="motion_agent_failed",



                error=motion_response.get(



                    "error",



                    (

                        "Motion Agent returned "

                        "unsuccessful response."

                    ),



                ),



            )





        # ====================================================

        # MOTION STEP 6 — GET OUTPUT

        # ====================================================



        motion_output = motion_response.get(

            "output"

        )





        if motion_output is None:



            return mark_agent_failed(



                state=state,



                agent_id="motion_agent",



                stage="motion_agent_failed",



                error=(

                    "Motion Agent returned success "

                    "but output is missing."

                ),



            )





        # ====================================================

        # MOTION STEP 7 — STORE PHASE-1 RECEIPT

        # ====================================================



        state.artifacts[

            "motion_phase1_receipt"

        ] = motion_output





        # ====================================================

        # MOTION STEP 8 — MARK MOTION AGENT COMPLETED

        # ====================================================



        state.agent_tasks[

            "motion_agent"

        ].status = AgentTaskStatus.COMPLETED





        state.agent_tasks[

            "motion_agent"

        ].output = motion_output





        state.agent_tasks[

            "motion_agent"

        ].error = None





        print(

            "[MANAGER] motion_agent status = COMPLETED"

        )





        # ====================================================

        # MOTION STEP 9 — PHASE-1B STOP POINT

        # ====================================================



        state.current_agent = None



        state.current_stage = (

            "motion_plan_received"

        )



        state.next_agent = None



        state.status = WorkflowStatus.RUNNING





        save_job(state)





        print(

            "[MANAGER] "

            "Motion Agent successfully received Planner plan"

        )



        print(

            "[MANAGER] "

            "Phase-1B Motion communication test = PASSED"

        )



        print(

            "[MANAGER] Workflow state saved"

        )



        print("=" * 70 + "\n")





        # ====================================================

        # IMPORTANT:

        #

        # Motion job এখানেই return করতে হবে।

        #

        # Otherwise execution নিচের existing Graphic Agent

        # section-এ fall-through করবে।

        # ====================================================



        return state





    # ========================================================

    # GRAPHIC ROUTE SAFETY GATE

    # ========================================================

    #

    # এই point-এ শুধু graphic_agent থাকার কথা।

    #

    # Existing Graphic Agent code নিচে unchanged থাকবে।

    # ========================================================



    if execution_agent != "graphic_agent":



        state.status = WorkflowStatus.FAILED



        state.current_stage = (

            "execution_agent_routing_failed"

        )



        state.current_agent = None



        state.next_agent = None



        save_job(state)



        print(

            "[MANAGER] Unsupported execution route: "

            f"{execution_agent}"

        )



        return state







    # ========================================================

    # STEP 17 — MARK GRAPHIC AGENT RUNNING

    # ========================================================

    #

    # PHASE-1 COMMUNICATION TEST

    #

    # এখনো Graphic Agent:

    #

    # - image generate করবে না

    # - Photoshop call করবে না

    # - Illustrator call করবে না

    # - LLM call করবে না

    #

    # শুধু Planner plan Manager থেকে receive করতে পারে

    # কিনা সেটা verify করা হচ্ছে।

    # ========================================================



    state.current_stage = "graphic_agent"



    state.current_agent = "graphic_agent"



    state.next_agent = None



    state.agent_tasks[

        "graphic_agent"

    ].status = AgentTaskStatus.RUNNING



    save_job(state)



    print()



    print("-" * 70)



    print(

        "[MANAGER] Assigning Planner plan to graphic_agent"

    )



    print(

        "[MANAGER] graphic_agent status = RUNNING"

    )





    # ========================================================

    # STEP 18 — PREPARE GRAPHIC AGENT PAYLOAD

    # ========================================================

    #

    # Planner-এর verified final_output direct পাঠানো হচ্ছে।

    #

    # Manager plan modify করছে না।

    # Manager design করছে না।

    # ========================================================



    graphic_payload = {



        "job_id":

            state.job_id,



        "planner_plan":

            planner_output,



        "original_user_request":

            state.original_prompt,



        "selected_image_model":

        state.selected_image_model,    



        # Loop Engineering:

        # Graphic Agent validation bounded থাকবে।

        "max_validation_attempts":

            2,

    }



    print(

        "[MANAGER] Sending Planner plan to graphic_agent..."

    )





    # ========================================================

    # STEP 19 — DISPATCH TO GRAPHIC AGENT

    # ========================================================



    try:



        graphic_response = await dispatch_to_agent(



            agent_id="graphic_agent",



            payload=graphic_payload,

        )



    except Exception as exc:



        return mark_agent_failed(



            state=state,



            agent_id="graphic_agent",



            stage="graphic_agent_failed",



            error=exc,

        )





    # ========================================================

    # STEP 20 — RECEIVE GRAPHIC RESPONSE

    # ========================================================



    print(

        "[MANAGER] Response received from graphic_agent"

    )



    print()



    print(

        "[MANAGER] Graphic Agent returned this output:"

    )



    print(

        json.dumps(

            graphic_response,

            indent=2,

            ensure_ascii=False,

        )

    )



    print()





    # ========================================================

    # STEP 21 — BASIC RESPONSE VALIDATION

    # ========================================================

    #

    # Manager Graphic Agent-এর internal validation repeat

    # করবে না।

    #

    # Manager শুধু service-level success check করবে।

    # ========================================================



    if not graphic_response.get(

        "success"

    ):



        return mark_agent_failed(



            state=state,



            agent_id="graphic_agent",



            stage="graphic_agent_failed",



            error=graphic_response.get(



                "error",



                "Graphic Agent returned unsuccessful response."

            ),

        )





    # ========================================================

    # STEP 22 — STORE GRAPHIC PHASE-1 RECEIPT

    # ========================================================



    graphic_output = graphic_response.get(

        "output"

    )



    state.artifacts[

        "graphic_phase1_receipt"

    ] = graphic_output





    # ========================================================

    # STEP 23 — MARK GRAPHIC AGENT COMPLETED

    # ========================================================



    state.agent_tasks[

        "graphic_agent"

    ].status = AgentTaskStatus.COMPLETED



    state.agent_tasks[

        "graphic_agent"

    ].output = graphic_output



    state.agent_tasks[

        "graphic_agent"

    ].error = None



    print(

        "[MANAGER] graphic_agent status = COMPLETED"

    )





    # ========================================================

    # STEP 24 — PHASE-1 STOP POINT

    # ========================================================

    #

    # Graphic Agent successfully Planner plan receive করেছে।

    #

    # কিন্তু real design generation এখনো শুরু হয়নি।

    #

    # তাই এই stage-এর নাম intentionally:

    #

    # graphic_plan_received

    #

    # Future Phase-2 থেকে এখান থেকে Graphic reasoning /

    # tool selection শুরু হবে।

    # ========================================================



    state.current_agent = None



    state.current_stage = "graphic_plan_received"



    state.next_agent = None



    # Full product workflow এখনো complete নয়।

    # Graphic generation future phase-এ বাকি।

    state.status = WorkflowStatus.RUNNING



    # ============================================================

    # NEW:

    # Mirror graphic artifact into manager artifacts store

    # ============================================================



    graphic_artifact = (
    # --------------------------------------------------------
    # Case 1:
    # Graphic Agent returns artifact directly at response level.
    # --------------------------------------------------------
    graphic_response.get(
        "artifact"
    )

    or

    # --------------------------------------------------------
    # Case 2:
    # Artifact exists inside the already extracted
    # graphic_output dictionary.
    # --------------------------------------------------------
    (
        graphic_output.get(
            "artifact"
        )
        if isinstance(
            graphic_output,
            dict,
        )
        else None
    )

    or

    # --------------------------------------------------------
    # Case 3:
    # Artifact exists under:
    #
    # graphic_response["output"]["artifact"]
    # --------------------------------------------------------
    (
        graphic_response
        .get(
            "output",
            {},
        )
        .get(
            "artifact"
        )
        if isinstance(
            graphic_response.get(
                "output",
                {},
            ),
            dict,
        )
        else None
    )
)


# ============================================================
# STORE ARTIFACT METADATA
# ============================================================
#
# Expected artifact example:
#
# {
#     "format": "jpg",
#     "filename": "design.jpg",
#     "preview_url": "...",
#     "download_url": "..."
# }
#
# Manager does NOT modify this data.
# ============================================================

    if isinstance(
        graphic_artifact,
        dict,
    ):
        state.artifacts[
            "graphic_artifact"
        ] = graphic_artifact



    save_job(state)



    print(

        "[MANAGER] Graphic Agent successfully received Planner plan"

    )



    print(

        "[MANAGER] Phase-1 Graphic communication test = PASSED"

    )



    print(

        "[MANAGER] Workflow state saved"

    )



    print("=" * 70 + "\n")



    return state











# """
# Manager Agent Workflow

# PHASE 1 FLOW:

# User Prompt

#     ↓

# Manager

#     ↓

# Create Job

#     ↓

# Prompt-to-JSON Agent

#     ↓

# Receive JSON

#     ↓

# Track Completed

#     ↓

# Set Planner as Next Agent

# IMPORTANT:

# এই Phase-এ Planner execute হবে না।

# """

# from __future__ import annotations

# import uuid

# from typing import Dict

# import json

# from packages.manager_agent.orchestrator.dispatcher import (
#     dispatch_to_agent,
# )

# from packages.manager_agent.orchestrator.state import (
#     AgentTaskStatus,
#     ManagerWorkflowState,
#     WorkflowStatus,
# )

# # ============================================================
# # ADDED: DETERMINISTIC SPECIALIZED-AGENT ROUTING
# # ============================================================

# def select_execution_agent(
#     planner_output: dict,
# ) -> str:
#     """
#     Select specialized execution agent from Planner output.

#     IMPORTANT:

#     This function does NOT:
#     - plan
#     - design
#     - generate motion
#     - choose Wan/LTX
#     - choose Illustrator/Photoshop tools

#     It only performs deterministic orchestration routing.
#     """

#     primary_job_type = planner_output.get(
#         "primary_job_type"
#     )

#     if primary_job_type == "graphic_design":

#         return "graphic_agent"

#     if primary_job_type == "motion_design":

#         return "motion_agent"

#     raise ValueError(
#         "Manager cannot route Planner output. "
#         f"Unsupported primary_job_type: "
#         f"{primary_job_type!r}"
#     )


# # ============================================================
# # TEMPORARY IN-MEMORY JOB STORE
# # ============================================================

# # Phase-1 testing-এর জন্য memory store ব্যবহার করছি।
# #
# # পরে এটি replace করা যাবে:
# # - PostgreSQL
# # - Redis
# # - Durable workflow store
# #
# # কিন্তু এখন architecture test করার জন্য যথেষ্ট।

# JOB_STORE: Dict[str, ManagerWorkflowState] = {}


# # ============================================================
# # CREATE NEW JOB
# # ============================================================

# def create_job(user_prompt: str,
#     selected_image_model: str | None = None,
# ) -> ManagerWorkflowState:
#     """
#     User prompt থেকে নতুন Manager workflow তৈরি করে।
#     """

#     job_id = str(uuid.uuid4())

#     state = ManagerWorkflowState(
#         job_id=job_id,
#         original_prompt=user_prompt,
#         selected_image_model=selected_image_model,
#         status=WorkflowStatus.CREATED,
#         current_stage="manager_received",
#         current_agent=None,
#         next_agent="prompt_to_json_agent",
#     )

#     # Job store করো
#     JOB_STORE[job_id] = state

#     return state


# # ============================================================
# # SAVE / UPDATE JOB
# # ============================================================

# def save_job(state: ManagerWorkflowState) -> None:
#     """
#     Updated state memory-তে save করে।
#     """

#     JOB_STORE[state.job_id] = state


# # ============================================================
# # GET JOB
# # ============================================================

# def get_job(job_id: str) -> ManagerWorkflowState:
#     """
#     Job ID দিয়ে workflow state return করে।
#     """

#     state = JOB_STORE.get(job_id)

#     if not state:
#         raise ValueError(
#             f"Job '{job_id}' not found."
#         )

#     return state


# # ============================================================
# # GENERIC AGENT FAILURE TRACKER
# # ============================================================
# #
# # ADDED:
# #
# # Previously the single except block always marked
# # prompt_to_json_agent as failed.
# #
# # That becomes incorrect once Planner Agent exists.
# #
# # This helper allows Manager to fail the CURRENT agent
# # without mixing agent-specific business logic.
# # ============================================================

# def mark_agent_failed(
#     state: ManagerWorkflowState,
#     agent_id: str,
#     stage: str,
#     error: Exception | str,
# ) -> ManagerWorkflowState:
#     """
#     Mark one agent execution as failed.

#     This is orchestration/state-management logic only.
#     """

#     error_message = str(error)

#     state.status = WorkflowStatus.FAILED

#     state.current_stage = stage

#     state.current_agent = agent_id

#     state.next_agent = None

#     # Only update the requested agent.
#     if agent_id in state.agent_tasks:

#         state.agent_tasks[
#             agent_id
#         ].status = AgentTaskStatus.FAILED

#         state.agent_tasks[
#             agent_id
#         ].error = error_message

#     save_job(state)

#     print(
#         f"[MANAGER] {agent_id} status = FAILED"
#     )

#     print(
#         f"[MANAGER] Error: {error_message}"
#     )

#     return state


# # ============================================================
# # MANAGER PHASE-1 WORKFLOW
# # ============================================================

# async def run_manager_workflow(
#     user_prompt: str,
#     selected_image_model: str | None = None,
# ) -> ManagerWorkflowState:

#     print("\n" + "=" * 70)

#     print("[MANAGER] Received user prompt")

#     print(f"[MANAGER] Prompt: {user_prompt}")

#     print("=" * 70)

#     """
#     Phase-1 Manager Workflow.

#     এই function:

#     1. Job তৈরি করবে

#     2. Prompt-to-JSON Agent running mark করবে

#     3. User prompt JSON Agent-এ পাঠাবে

#     4. Result receive করবে

#     5. Result store করবে

#     6. Agent completed mark করবে

#     7. next_agent = planner_agent set করবে
#     """

#     # ========================================================
#     # STEP 1 — CREATE JOB
#     # ========================================================

#     state = create_job(
#         user_prompt,
#         selected_image_model=selected_image_model
#     )

#     print(f"[MANAGER] Job created: {state.job_id}")

#     state.status = WorkflowStatus.RUNNING

#     state.current_stage = "prompt_to_json"

#     state.current_agent = "prompt_to_json_agent"

#     state.next_agent = None

#     state.agent_tasks[
#         "prompt_to_json_agent"
#     ].status = AgentTaskStatus.RUNNING

#     save_job(state)

#     print("[MANAGER] prompt_to_json_agent status = RUNNING")

#     # ========================================================
#     # STEP 2 — PREPARE PAYLOAD
#     # ========================================================

#     prompt_agent_payload = {
#         "job_id": state.job_id,
#         "prompt": state.original_prompt,
#     }

#     print("[MANAGER] Sending prompt to prompt_to_json_agent...")

#     # ========================================================
#     # STEP 3 — SEND TASK TO PROMPT-TO-JSON AGENT
#     # ========================================================

#     try:

#         response = await dispatch_to_agent(
#             agent_id="prompt_to_json_agent",
#             payload=prompt_agent_payload,
#         )

#         print("[MANAGER] Response received from prompt_to_json_agent")

#         print("\n[MANAGER] JSON Agent returned this output:")

#         print(
#             json.dumps(
#                 response,
#                 indent=2,
#                 ensure_ascii=False,
#             )
#         )

#         print()

#         # ====================================================
#         # STEP 4 — VALIDATE BASIC AGENT RESPONSE
#         # ====================================================

#         if not response.get("success"):

#             raise RuntimeError(
#                 response.get(
#                     "error",
#                     "Prompt-to-JSON Agent returned unsuccessful response."
#                 )
#             )

#         # ====================================================
#         # STEP 5 — STORE AGENT OUTPUT
#         # ====================================================

#         prompt_json_output = response.get("output")

#         print("[MANAGER] JSON output received successfully")

#         state.artifacts[
#             "prompt_json"
#         ] = prompt_json_output

#         # ====================================================
#         # STEP 6 — MARK JSON AGENT COMPLETED
#         # ====================================================

#         state.agent_tasks[
#             "prompt_to_json_agent"
#         ].status = AgentTaskStatus.COMPLETED

#         state.agent_tasks[
#             "prompt_to_json_agent"
#         ].output = prompt_json_output

#         print(
#             "[MANAGER] prompt_to_json_agent status = COMPLETED"
#         )

#         # ====================================================
#         # STEP 7 — MOVE WORKFLOW TO NEXT STAGE
#         # ====================================================

#         state.current_agent = None

#         state.current_stage = "prompt_to_json_completed"

#         # Planner execution এখনো করবো না।
#         # শুধু Manager জানবে next step কী।

#         state.next_agent = "planner_agent"

#         save_job(state)

#         print("[MANAGER] Workflow state saved")

#         print("[MANAGER] Next agent = planner_agent")

#     # ========================================================
#     # ERROR HANDLING
#     # ========================================================

#     except Exception as exc:

#         print(f"[MANAGER] ERROR: {exc}")

#         state.status = WorkflowStatus.FAILED

#         state.current_stage = "prompt_to_json_failed"

#         state.agent_tasks[
#             "prompt_to_json_agent"
#         ].status = AgentTaskStatus.FAILED

#         state.agent_tasks[
#             "prompt_to_json_agent"
#         ].error = str(exc)

#         save_job(state)

#         print(
#             "[MANAGER] prompt_to_json_agent status = FAILED"
#         )

#         return state


#     # ========================================================
#     # ADDED — PLANNER AGENT EXECUTION
#     # ========================================================
#     #
#     # IMPORTANT:
#     #
#     # JSON Agent-এর existing logic এখানে change করা হয়নি।
#     #
#     # এখন JSON Agent successfully complete হওয়ার পরে
#     # Manager Planner Agent-কে task assign করবে।
#     #
#     # Manager Planner-এর internal planning logic জানবে না।
#     #
#     # Planner-এর:
#     #
#     # - planning
#     # - validation
#     # - verification
#     # - repair
#     # - hill-climbing
#     #
#     # সব Planner Agent-এর নিজের graph-এর ভিতরে হবে।
#     #
#     # Manager শুধু:
#     #
#     # assign
#     # track
#     # receive
#     # store
#     #
#     # করবে।
#     # ========================================================


#     # ========================================================
#     # STEP 8 — MARK PLANNER AGENT RUNNING
#     # ========================================================

#     state.current_stage = "planner"

#     state.current_agent = "planner_agent"

#     state.next_agent = None

#     state.agent_tasks[
#         "planner_agent"
#     ].status = AgentTaskStatus.RUNNING

#     save_job(state)

#     print()

#     print("-" * 70)

#     print(
#         "[MANAGER] Assigning task to planner_agent"
#     )

#     print(
#         "[MANAGER] planner_agent status = RUNNING"
#     )


#     # ========================================================
#     # STEP 9 — PREPARE PLANNER PAYLOAD
#     # ========================================================
#     #
#     # ADDED:
#     #
#     # Planner Agent-এর API contract অনুযায়ী
#     # Manager নিচের data পাঠাবে:
#     #
#     # - same job_id
#     # - JSON Agent output
#     # - original user request
#     # - maximum repair attempts
#     #
#     # Manager এখানে planning করছে না।
#     # ========================================================

#     planner_payload = {

#         "job_id": state.job_id,

#         "json_agent_output": prompt_json_output,

#         "original_user_request": state.original_prompt,

#         # Planner-এর verification / hill-climbing loop
#         # bounded রাখার জন্য maximum repair limit।
#         "max_repair_attempts": 3,
#     }

#     print(
#         "[MANAGER] Sending JSON requirements to planner_agent..."
#     )


#     # ========================================================
#     # STEP 10 — SEND TASK TO PLANNER AGENT
#     # ========================================================

#     try:

#         planner_response = await dispatch_to_agent(
#             agent_id="planner_agent",
#             payload=planner_payload,
#         )

#     except Exception as exc:

#         # ====================================================
#         # ADDED:
#         # Planner failure হলে JSON Agent-কে FAILED করা হবে না।
#         #
#         # যে agent fail করেছে শুধু তাকেই FAILED করা হবে।
#         # ====================================================

#         return mark_agent_failed(
#             state=state,
#             agent_id="planner_agent",
#             stage="planner_failed",
#             error=exc,
#         )


#     # ========================================================
#     # STEP 11 — RECEIVE PLANNER RESPONSE
#     # ========================================================

#     print(
#         "[MANAGER] Response received from planner_agent"
#     )

#     print()

#     print(
#         "[MANAGER] Planner Agent returned this output:"
#     )

#     # ========================================================
#     # ADDED:
#     #
#     # Planner Agent Manager-কে যে complete JSON return করেছে
#     # সেটা terminal-এ print হবে।
#     #
#     # এতে আমরা confirm করতে পারবো:
#     #
#     # - Planner কাজ receive করেছে
#     # - planning complete হয়েছে
#     # - loop run হয়েছে কি না
#     # - verification score
#     # - final plan
#     # ========================================================

#     print(
#         json.dumps(
#             planner_response,
#             indent=2,
#             ensure_ascii=False,
#         )
#     )

#     print()


#     # ========================================================
#     # STEP 12 — VALIDATE BASIC PLANNER RESPONSE
#     # ========================================================
#     #
#     # IMPORTANT:
#     #
#     # Manager Planner-এর plan আবার verify করবে না।
#     #
#     # Planner Agent already internally করেছে:
#     #
#     # planning
#     #     ↓
#     # validation
#     #     ↓
#     # verification
#     #     ↓
#     # repair / hill-climbing if needed
#     #     ↓
#     # finalization
#     #
#     # Manager শুধু success / failure check করছে।
#     # ========================================================

#     if not planner_response.get("success"):

#         return mark_agent_failed(
#             state=state,
#             agent_id="planner_agent",
#             stage="planner_failed",
#             error=planner_response.get(
#                 "error",
#                 "Planner Agent returned unsuccessful response."
#             ),
#         )


#     # ========================================================
#     # STEP 13 — GET FINAL PLANNER OUTPUT
#     # ========================================================

#     planner_output = planner_response.get(
#         "final_output"
#     )

#     # ========================================================
#     # ADDED:
#     #
#     # Planner success বলেছে কিন্তু final plan না থাকলে
#     # সেটা valid completion না।
#     # ========================================================

#     if planner_output is None:

#         return mark_agent_failed(
#             state=state,
#             agent_id="planner_agent",
#             stage="planner_failed",
#             error=(
#                 "Planner Agent returned success "
#                 "but final_output is missing."
#             ),
#         )


#     # ========================================================
#     # STEP 14 — STORE PLANNER OUTPUT
#     # ========================================================

#     state.artifacts[
#         "planner_plan"
#     ] = planner_output


#     # ========================================================
#     # ADDED — STORE PLANNER EXECUTION METADATA
#     # ========================================================
#     #
#     # Planner-এর actual plan থেকে runtime metadata আলাদা
#     # রাখা হচ্ছে।
#     #
#     # এতে business output clean থাকবে।
#     #
#     # Future observability/debugging সহজ হবে।
#     # ========================================================

#     state.artifacts[
#         "planner_metadata"
#     ] = {

#         "planning_iteration": planner_response.get(
#             "planning_iteration",
#             0,
#         ),

#         "repair_attempt": planner_response.get(
#             "repair_attempt",
#             0,
#         ),

#         "verification_score": planner_response.get(
#             "verification_score",
#             0.0,
#         ),

#         "best_score": planner_response.get(
#             "best_score",
#             0.0,
#         ),
#     }


#     # ========================================================
#     # STEP 15 — MARK PLANNER AGENT COMPLETED
#     # ========================================================

#     state.agent_tasks[
#         "planner_agent"
#     ].status = AgentTaskStatus.COMPLETED

#     state.agent_tasks[
#         "planner_agent"
#     ].output = planner_output

#     state.agent_tasks[
#         "planner_agent"
#     ].error = None

#     print(
#         "[MANAGER] planner_agent status = COMPLETED"
#     )


#     # ========================================================
#     # STEP 16 — MOVE WORKFLOW TO NEXT STAGE
#     # ========================================================
#     #
#     # ADDED:
#     #
#     # Planner complete হওয়ার পরে Manager শুধু জানবে
#     # next job কোন agent-এর।
#     #
#     # Graphic Agent এখন execute করা হচ্ছে না।
#     #
#     # Graphic Agent implementation future step।
#     # ========================================================

#     # ========================================================
#     # CHANGED — ROUTE PLANNER OUTPUT TO SPECIALIZED AGENT
#     # ========================================================
#     #
#     # Previously:
#     #
#     #     Planner
#     #        ↓
#     #     graphic_agent
#     #
#     # was hardcoded.
#     #
#     # Now:
#     #
#     #     primary_job_type = graphic_design
#     #                ↓
#     #          graphic_agent
#     #
#     #     primary_job_type = motion_design
#     #                ↓
#     #           motion_agent
#     #
#     # Manager still performs orchestration only.
#     # ========================================================

#     try:

#         execution_agent = select_execution_agent(
#             planner_output
#         )

#     except Exception as exc:

#         state.status = WorkflowStatus.FAILED

#         state.current_stage = (
#             "execution_agent_routing_failed"
#         )

#         state.current_agent = None

#         state.next_agent = None

#         save_job(state)

#         print(
#             "[MANAGER] Execution-agent routing = FAILED"
#         )

#         print(
#             f"[MANAGER] Error: {exc}"
#         )

#         return state


#     # ========================================================
#     # ROUTING SUCCESS
#     # ========================================================

#     state.current_agent = None

#     state.current_stage = "planner_completed"

#     state.next_agent = execution_agent

#     state.status = WorkflowStatus.RUNNING

#     save_job(state)


#     print(
#         "[MANAGER] Planner output stored"
#     )

#     print(
#         "[MANAGER] Workflow state saved"
#     )

#     print(
#         f"[MANAGER] Next agent = {execution_agent}"
#     )


#     # ========================================================
#     # ADDED — MOTION AGENT EXECUTION BRANCH
#     # ========================================================
#     #
#     # IMPORTANT:
#     #
#     # If Planner classified the job as:
#     #
#     #     primary_job_type = motion_design
#     #
#     # Manager dispatches the same verified Planner output
#     # directly to Motion Agent.
#     #
#     # Manager does NOT:
#     #
#     # - modify the motion plan
#     # - create video prompts
#     # - select Wan
#     # - select LTX
#     # - run FFmpeg
#     #
#     # Existing Graphic Agent path below remains unchanged.
#     # ========================================================

#     if execution_agent == "motion_agent":


#         # ====================================================
#         # MOTION STEP 1 — MARK MOTION AGENT RUNNING
#         # ====================================================

#         state.current_stage = "motion_agent"

#         state.current_agent = "motion_agent"

#         state.next_agent = None


#         state.agent_tasks[
#             "motion_agent"
#         ].status = AgentTaskStatus.RUNNING


#         save_job(state)


#         print()

#         print("-" * 70)

#         print(
#             "[MANAGER] Assigning Planner plan to motion_agent"
#         )

#         print(
#             "[MANAGER] motion_agent status = RUNNING"
#         )


#         # ====================================================
#         # MOTION STEP 2 — PREPARE MOTION PAYLOAD
#         # ====================================================

#         motion_payload = {

#             "job_id":
#                 state.job_id,

#             "planner_plan":
#                 planner_output,

#             "original_user_request":
#                 state.original_prompt,

#             "max_validation_attempts":
#                 2,

#         }


#         print(
#             "[MANAGER] Sending Planner plan to motion_agent..."
#         )


#         # ====================================================
#         # MOTION STEP 3 — DISPATCH TO MOTION AGENT
#         # ====================================================

#         try:

#             motion_response = await dispatch_to_agent(

#                 agent_id="motion_agent",

#                 payload=motion_payload,

#             )

#         except Exception as exc:

#             return mark_agent_failed(

#                 state=state,

#                 agent_id="motion_agent",

#                 stage="motion_agent_failed",

#                 error=exc,

#             )


#         # ====================================================
#         # MOTION STEP 4 — RECEIVE RESPONSE
#         # ====================================================

#         print(
#             "[MANAGER] Response received from motion_agent"
#         )

#         print()

#         print(
#             "[MANAGER] Motion Agent returned this output:"
#         )

#         print(
#             json.dumps(
#                 motion_response,
#                 indent=2,
#                 ensure_ascii=False,
#             )
#         )

#         print()


#         # ====================================================
#         # MOTION STEP 5 — BASIC RESPONSE VALIDATION
#         # ====================================================
#         #
#         # Manager Motion Agent-এর internal validation
#         # repeat করবে না।
#         #
#         # Manager শুধু service-level success check করবে।
#         # ====================================================

#         if not motion_response.get(
#             "success"
#         ):

#             return mark_agent_failed(

#                 state=state,

#                 agent_id="motion_agent",

#                 stage="motion_agent_failed",

#                 error=motion_response.get(

#                     "error",

#                     (
#                         "Motion Agent returned "
#                         "unsuccessful response."
#                     ),

#                 ),

#             )


#         # ====================================================
#         # MOTION STEP 6 — GET OUTPUT
#         # ====================================================

#         motion_output = motion_response.get(
#             "output"
#         )


#         if motion_output is None:

#             return mark_agent_failed(

#                 state=state,

#                 agent_id="motion_agent",

#                 stage="motion_agent_failed",

#                 error=(
#                     "Motion Agent returned success "
#                     "but output is missing."
#                 ),

#             )


#         # ====================================================
#         # MOTION STEP 7 — STORE PHASE-1 RECEIPT
#         # ====================================================

#         state.artifacts[
#             "motion_phase1_receipt"
#         ] = motion_output


#         # ====================================================
#         # MOTION STEP 8 — MARK MOTION AGENT COMPLETED
#         # ====================================================

#         state.agent_tasks[
#             "motion_agent"
#         ].status = AgentTaskStatus.COMPLETED


#         state.agent_tasks[
#             "motion_agent"
#         ].output = motion_output


#         state.agent_tasks[
#             "motion_agent"
#         ].error = None


#         print(
#             "[MANAGER] motion_agent status = COMPLETED"
#         )


#         # ====================================================
#         # MOTION STEP 9 — PHASE-1B STOP POINT
#         # ====================================================

#         state.current_agent = None

#         state.current_stage = (
#             "motion_plan_received"
#         )

#         state.next_agent = None

#         state.status = WorkflowStatus.RUNNING


#         save_job(state)


#         print(
#             "[MANAGER] "
#             "Motion Agent successfully received Planner plan"
#         )

#         print(
#             "[MANAGER] "
#             "Phase-1B Motion communication test = PASSED"
#         )

#         print(
#             "[MANAGER] Workflow state saved"
#         )

#         print("=" * 70 + "\n")


#         # ====================================================
#         # IMPORTANT:
#         #
#         # Motion job এখানেই return করতে হবে।
#         #
#         # Otherwise execution নিচের existing Graphic Agent
#         # section-এ fall-through করবে।
#         # ====================================================

#         return state


#     # ========================================================
#     # GRAPHIC ROUTE SAFETY GATE
#     # ========================================================
#     #
#     # এই point-এ শুধু graphic_agent থাকার কথা।
#     #
#     # Existing Graphic Agent code নিচে unchanged থাকবে।
#     # ========================================================

#     if execution_agent != "graphic_agent":

#         state.status = WorkflowStatus.FAILED

#         state.current_stage = (
#             "execution_agent_routing_failed"
#         )

#         state.current_agent = None

#         state.next_agent = None

#         save_job(state)

#         print(
#             "[MANAGER] Unsupported execution route: "
#             f"{execution_agent}"
#         )

#         return state

    

#     # ========================================================
#     # STEP 17 — MARK GRAPHIC AGENT RUNNING
#     # ========================================================
#     #
#     # PHASE-1 COMMUNICATION TEST
#     #
#     # এখনো Graphic Agent:
#     #
#     # - image generate করবে না
#     # - Photoshop call করবে না
#     # - Illustrator call করবে না
#     # - LLM call করবে না
#     #
#     # শুধু Planner plan Manager থেকে receive করতে পারে
#     # কিনা সেটা verify করা হচ্ছে।
#     # ========================================================

#     state.current_stage = "graphic_agent"

#     state.current_agent = "graphic_agent"

#     state.next_agent = None

#     state.agent_tasks[
#         "graphic_agent"
#     ].status = AgentTaskStatus.RUNNING

#     save_job(state)

#     print()

#     print("-" * 70)

#     print(
#         "[MANAGER] Assigning Planner plan to graphic_agent"
#     )

#     print(
#         "[MANAGER] graphic_agent status = RUNNING"
#     )


#     # ========================================================
#     # STEP 18 — PREPARE GRAPHIC AGENT PAYLOAD
#     # ========================================================
#     #
#     # Planner-এর verified final_output direct পাঠানো হচ্ছে।
#     #
#     # Manager plan modify করছে না।
#     # Manager design করছে না।
#     # ========================================================

#     graphic_payload = {

#         "job_id":
#             state.job_id,

#         "planner_plan":
#             planner_output,

#         "original_user_request":
#             state.original_prompt,

#         "selected_image_model":
#         state.selected_image_model,    

#         # Loop Engineering:
#         # Graphic Agent validation bounded থাকবে।
#         "max_validation_attempts":
#             2,
#     }

#     print(
#         "[MANAGER] Sending Planner plan to graphic_agent..."
#     )


#     # ========================================================
#     # STEP 19 — DISPATCH TO GRAPHIC AGENT
#     # ========================================================

#     try:

#         graphic_response = await dispatch_to_agent(

#             agent_id="graphic_agent",

#             payload=graphic_payload,
#         )

#     except Exception as exc:

#         return mark_agent_failed(

#             state=state,

#             agent_id="graphic_agent",

#             stage="graphic_agent_failed",

#             error=exc,
#         )


#     # ========================================================
#     # STEP 20 — RECEIVE GRAPHIC RESPONSE
#     # ========================================================

#     print(
#         "[MANAGER] Response received from graphic_agent"
#     )

#     print()

#     print(
#         "[MANAGER] Graphic Agent returned this output:"
#     )

#     print(
#         json.dumps(
#             graphic_response,
#             indent=2,
#             ensure_ascii=False,
#         )
#     )

#     print()


#     # ========================================================
#     # STEP 21 — BASIC RESPONSE VALIDATION
#     # ========================================================
#     #
#     # Manager Graphic Agent-এর internal validation repeat
#     # করবে না।
#     #
#     # Manager শুধু service-level success check করবে।
#     # ========================================================

#     if not graphic_response.get(
#         "success"
#     ):

#         return mark_agent_failed(

#             state=state,

#             agent_id="graphic_agent",

#             stage="graphic_agent_failed",

#             error=graphic_response.get(

#                 "error",

#                 "Graphic Agent returned unsuccessful response."
#             ),
#         )


#     # ========================================================
#     # STEP 22 — STORE GRAPHIC PHASE-1 RECEIPT
#     # ========================================================

#     graphic_output = graphic_response.get(
#         "output"
#     )

#     state.artifacts[
#         "graphic_phase1_receipt"
#     ] = graphic_output


#     # ========================================================
#     # STEP 23 — MARK GRAPHIC AGENT COMPLETED
#     # ========================================================

#     state.agent_tasks[
#         "graphic_agent"
#     ].status = AgentTaskStatus.COMPLETED

#     state.agent_tasks[
#         "graphic_agent"
#     ].output = graphic_output

#     state.agent_tasks[
#         "graphic_agent"
#     ].error = None

#     print(
#         "[MANAGER] graphic_agent status = COMPLETED"
#     )


#     # ========================================================
#     # STEP 24 — PHASE-1 STOP POINT
#     # ========================================================
#     #
#     # Graphic Agent successfully Planner plan receive করেছে।
#     #
#     # কিন্তু real design generation এখনো শুরু হয়নি।
#     #
#     # তাই এই stage-এর নাম intentionally:
#     #
#     # graphic_plan_received
#     #
#     # Future Phase-2 থেকে এখান থেকে Graphic reasoning /
#     # tool selection শুরু হবে।
#     # ========================================================

#     state.current_agent = None

#     state.current_stage = "graphic_plan_received"

#     state.next_agent = None

#     # Full product workflow এখনো complete নয়।
#     # Graphic generation future phase-এ বাকি।
#     state.status = WorkflowStatus.RUNNING

#     # ============================================================
#     # NEW:
#     # Mirror graphic artifact into manager artifacts store
#     # ============================================================

#     graphic_artifact = (
#         graphic_result.get("artifact")
#         or
#         (
#             graphic_result
#             .get("output", {})
#             .get("artifact")
#         )
#     )

#     if graphic_artifact:
#         state.artifacts["graphic_artifact"] = (
#             graphic_artifact
#         )

#     save_job(state)

#     print(
#         "[MANAGER] Graphic Agent successfully received Planner plan"
#     )

#     print(
#         "[MANAGER] Phase-1 Graphic communication test = PASSED"
#     )

#     print(
#         "[MANAGER] Workflow state saved"
#     )

#     print("=" * 70 + "\n")

#     return state



