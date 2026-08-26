from fastapi import APIRouter

from app.api import health, projects

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(projects.router)
