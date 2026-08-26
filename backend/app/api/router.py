from fastapi import APIRouter

from app.api import (
    audit,
    auth,
    builds,
    credentials,
    deployments,
    health,
    mcp_access,
    projects,
    settings,
    sources,
    users,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(projects.router)
router.include_router(sources.router)
router.include_router(credentials.router)
router.include_router(deployments.router)
router.include_router(mcp_access.router)
router.include_router(settings.router)
router.include_router(audit.router)
router.include_router(builds.router)
