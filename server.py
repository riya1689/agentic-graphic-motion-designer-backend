# server.py

"""
Central FastAPI Server

Development:
    All agent APIs run under one FastAPI application.

Production:
    Agents can later run as independent services and the
    Manager can route through the Agent Registry.
"""

from pathlib import Path
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv


# ============================================================
# PROJECT ROOT + ENVIRONMENT
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent

ENV_FILE = ROOT_DIR / ".env"

load_dotenv(
    dotenv_path=ENV_FILE,
    override=False,
)


# ============================================================
# IMPORTANT
#
# Agent imports MUST happen AFTER load_dotenv().
# Some agent modules initialize their LLM during import.
# ============================================================

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from packages.manager_agent.api.orchestrator_router import (
    create_manager_router,
)

# ============================================================
# NEW: PLANNER AGENT ROUTER
# ============================================================
#
# Planner Agent API central FastAPI server-এ register হবে।
#
# Planner-এর internal planning / verification /
# hill-climbing loop planner_agent-এর নিজের graph.py-তে থাকে।
#
# server.py শুধু HTTP route expose করে।
# ============================================================

from packages.graphic_agent.api.router import (
    router as graphic_router,
)

from packages.planner_agent.api.router import (
    router as planner_router,
)

from packages.motion_agent.api.router import (
    router as motion_router,
)

from packages.auth.api.router import create_auth_router
from packages.auth.api.dependencies import build_auth_dependencies
from packages.auth.infrastructure.postgres.config import AuthPostgresSettings
from packages.auth.infrastructure.postgres.factory import build_postgres_auth_service
from packages.provider_secrets.api.router import create_provider_secrets_router
from packages.provider_secrets.infrastructure.postgres.config import (
    ProviderSecretsPostgresSettings,
)
from packages.provider_secrets.infrastructure.postgres.factory import (
    build_provider_secret_service,
)
from packages.provider_secrets.application.runtime import (
    configure_runtime_provider_secret_resolver,
)

from packages.model_catalog.api.router import (
    router as model_catalog_router,
)
from packages.model_catalog.application.initialization import (
    initialize_model_catalog,
)
from packages.model_catalog.application.runtime import (
    catalog_service,
)
from packages.model_catalog.adapters.higgsfield import HiggsfieldCatalogAdapter
from packages.request_contract.application.direct_understanding import (
    LLMRequestUnderstandingService,
)
from packages.model_router import ModelRouter
from packages.planner_integration.application.service import (
    ConditionalPlannerService,
)
from packages.planner_integration.adapters.existing_planner import (
    ExistingPlannerAdapter,
)
from packages.planner_integration.adapters.logical_repair import (
    LogicalRepairingPlanner,
)
from packages.execution.application.executors import (
    GraphicExecutor,
    MotionExecutor,
)
from packages.execution.adapters.higgsfield.provider import (
    HiggsfieldExecutionAdapter,
)
from packages.execution.application.provider_registry import ProviderExecutionRegistry
from packages.verification.application.verifier import Verifier
from packages.verification.strategies.vision import GeminiVisionVerifier
from packages.verification.application.visual_inspection import DeterministicVisualInspector
from packages.verification.strategies.vision_inspection import GeminiVisionInspectionAdapter
from packages.orchestrator.application.orchestrator import Orchestrator
from packages.orchestrator.api.router import create_router as create_orchestrator_router
from packages.graphic_agent.native_svg import NativeSvgGraphicExecutor
from packages.graphic_agent.code_svg import GeminiCodeSvgExecutor
from packages.graphic_agent.image_to_vector import ImageToVectorExecutor
from packages.graphic_agent.hybrid_svg import HybridSvgExecutor, OpenAIRasterBackgroundProvider
from packages.graphic_agent.system_raster import SystemRasterGraphicExecutor
from packages.revision.adapters.gemini import GeminiRevisionPlanner
from packages.icon_library.api import create_icon_library_router
from packages.icon_library.infrastructure.postgres import (
    PostgresSettings,
    build_postgres_icon_library_service,
    check_postgres_connection,
)
from packages.icon_library.infrastructure.sqlite.factory import (
    build_sqlite_icon_library_service,
    check_sqlite_connection,
)
from packages.icon_library.infrastructure.google_drive.config import GoogleDriveIconSettings
from packages.icon_library.infrastructure.google_drive.oauth import GoogleDriveOAuthManager
from packages.icon_library.infrastructure.google_drive.sync import GoogleDriveIconSync
from packages.auth.infrastructure.sqlite.factory import build_sqlite_auth_service
from packages.provider_secrets.infrastructure.sqlite.factory import build_sqlite_provider_secret_service
from packages.sqlite_storage.bootstrap import initialize_database, seed_builtin_catalog
from packages.postgres_bootstrap import (
    format_migration_result,
    initialize_application_database,
    seed_application_catalog,
    should_auto_migrate,
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize local persistence and perform catalog discovery once."""
    if storage_backend == "sqlite":
        try:
            initialize_database()
        except Exception as exc:
            raise RuntimeError(
                "Encrypted SQLite initialization failed. Verify SQLCipher and "
                "Windows Credential Manager dependencies."
            ) from exc
        application.state.storage_backend = "sqlite"
        application.state.seeded_builtin_icons = seed_builtin_catalog(icon_library_service)
        if application.state.seeded_builtin_icons:
            print("Built-in icons seeded: " + ", ".join(application.state.seeded_builtin_icons))
    elif should_auto_migrate():
        try:
            migration_result = initialize_application_database(
                auth_settings=auth_settings,
                icon_library_settings=icon_library_settings,
            )
        except Exception as exc:
            raise RuntimeError(
                "PostgreSQL schema initialization failed. "
                "Grant the configured database user CREATE privileges, then "
                "restart the server. See docs/postgresql-setup.md."
            ) from exc
        application.state.postgres_migrations = migration_result
        application.state.seeded_builtin_icons = seed_application_catalog(
            icon_library_settings=icon_library_settings,
        )
        print(f"PostgreSQL migrations: {format_migration_result(migration_result)}")
        if application.state.seeded_builtin_icons:
            print(
                "Built-in icons seeded: "
                + ", ".join(application.state.seeded_builtin_icons)
            )

    result = initialize_model_catalog(catalog_service, HiggsfieldCatalogAdapter())
    application.state.model_catalog_initialization = result
    yield


def build_orchestrator() -> Orchestrator:
    """Compose the Phase 12 workflow once at the application boundary."""
    provider_registry = ProviderExecutionRegistry({
        "higgsfield": HiggsfieldExecutionAdapter(),
    })
    vision_inspector = (
        GeminiVisionInspectionAdapter()
        if os.getenv("VISION_INSPECTION_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        else None
    )
    revision_enabled = os.getenv("DESIGN_REVISION_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    revision_planner = GeminiRevisionPlanner() if revision_enabled else None
    try:
        max_revisions = max(1, min(int(os.getenv("MAX_DESIGN_REVISIONS", "3")), 3))
    except ValueError:
        max_revisions = 3
    return Orchestrator(
        understanding=LLMRequestUnderstandingService(),
        router=ModelRouter(catalog_service),
        planner=ConditionalPlannerService(
            LogicalRepairingPlanner(ExistingPlannerAdapter(prefer_focused_design=True))
        ),
        graphic_executor=GraphicExecutor(provider_registry),
        motion_executor=MotionExecutor(provider_registry),
        native_svg_executor=NativeSvgGraphicExecutor(),
        system_raster_executor=SystemRasterGraphicExecutor(),
        code_svg_executor=GeminiCodeSvgExecutor(),
        image_to_vector_executor=ImageToVectorExecutor(),
        hybrid_svg_executor=HybridSvgExecutor(
            foreground_executor=GeminiCodeSvgExecutor(),
            background_provider=OpenAIRasterBackgroundProvider(),
        ),
        verifier=Verifier(
            vision=GeminiVisionVerifier(),
            visual_inspector=DeterministicVisualInspector(),
            vision_inspector=vision_inspector,
        ),
        revision_planner=revision_planner,
        design_revision_enabled=revision_enabled,
        max_design_revisions=max_revisions,
    )


# ============================================================
# CREATE APPLICATION
# ============================================================

app = FastAPI(
    title="Agentic Graphic and Motion Designer",
    version="0.1.0",
    description=(
        "Central API server for the Agentic Graphic "
        "and Motion Designer multi-agent system."
    ),
    lifespan=lifespan,
)

# ============================================================
# FRONTEND CORS CONFIGURATION
# ============================================================
#
# IMPORTANT:
# This only defines HTTP access between frontend/backend.
# It does NOT mix frontend with agent business logic.
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173,"
            "http://tauri.localhost,tauri://localhost",
        ).split(",")
        if origin.strip()
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# ============================================================
# REGISTER ROUTERS
# ============================================================

storage_backend = os.getenv("STORAGE_BACKEND", "sqlite").strip().lower()
if storage_backend not in {"postgres", "sqlite"}:
    raise RuntimeError("STORAGE_BACKEND must be either 'postgres' or 'sqlite'.")

if storage_backend == "sqlite" and os.getenv("AGENTIC_DESKTOP_MODE", "").strip().lower() in {"1", "true", "yes", "on"}:
    from packages.sqlite_storage.runtime import ensure_desktop_runtime_secrets

    ensure_desktop_runtime_secrets()

icon_library_settings = PostgresSettings.from_environment()
auth_settings = AuthPostgresSettings.from_environment()
provider_secret_settings = ProviderSecretsPostgresSettings.from_environment()
drive_icon_settings = GoogleDriveIconSettings.from_environment()
if storage_backend == "sqlite":
    icon_library_service = build_sqlite_icon_library_service()
    auth_service = build_sqlite_auth_service(auth_settings)
    provider_secret_service = build_sqlite_provider_secret_service(provider_secret_settings)
    health_check = check_sqlite_connection
else:
    icon_library_service = build_postgres_icon_library_service(icon_library_settings)
    auth_service = build_postgres_auth_service(auth_settings)
    provider_secret_service = build_provider_secret_service(provider_secret_settings)
    health_check = lambda: check_postgres_connection(icon_library_settings)
auth_dependencies = build_auth_dependencies(auth_service)
drive_oauth = GoogleDriveOAuthManager(drive_icon_settings)
icon_drive_sync = GoogleDriveIconSync(icon_library_service, drive_icon_settings, drive_oauth)

# Provider adapters resolve encrypted admin-managed keys through this
# application boundary. They never import PostgreSQL repositories directly.
configure_runtime_provider_secret_resolver(provider_secret_service)
workflow_orchestrator = build_orchestrator()

app.include_router(
    create_auth_router(auth_service),
    prefix="/api",
)

app.include_router(
    create_provider_secrets_router(
        provider_secret_service,
        require_admin=auth_dependencies.require_role("admin"),
    ),
    prefix="/api",
)

app.include_router(
    create_manager_router(
        workflow_orchestrator,
        require_auth=auth_dependencies.require_auth,
    ),
    prefix="/api",
)

app.include_router(
    planner_router,
)

app.include_router(
    motion_router,
)

app.include_router(
    create_orchestrator_router(workflow_orchestrator),
    prefix="/api",
)

app.include_router(
    model_catalog_router,
    prefix="/api",
    dependencies=[Depends(auth_dependencies.require_auth)],
)

app.include_router(
    create_icon_library_router(
        icon_library_service,
        health_check=health_check,
        require_auth=auth_dependencies.require_auth,
        remote_sync=icon_drive_sync,
        require_admin=auth_dependencies.require_role("admin"),
    ),
    prefix="/api",
)


# ============================================================
# NEW: REGISTER PLANNER AGENT ROUTER
# ============================================================
#
# planner_agent/api/router.py already defines:
#
# prefix="/api/planner"
#
# IMPORTANT:
# ওই router-এর ভিতরে already "/api" আছে।
#
# তাই এখানে আবার prefix="/api" দিলে route হবে:
#
# /api/api/planner/plan
#
# যেটা ভুল।
#
# তাই Planner router direct register করা হচ্ছে।
# ============================================================

app.include_router(
    graphic_router,
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():
    return {
        "success": True,
        "message": "Agentic Graphic and Motion Designer API",
        "version": "0.1.0",
        "storage_backend": storage_backend,
        "docs": "/docs",
        "health": "/health",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health_check():
    return {
        "success": True,
        "status": "ok",
        "service": "agentic-graphic-motion-designer",
        "storage_backend": storage_backend,
    }



