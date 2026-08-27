from dataclasses import dataclass

from app.providers.ai.base import AIProvider
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.build_admission import BuildAdmissionDispatcher
from app.services.builds import BuildService
from app.services.cleanup import CleanupService
from app.services.credentials import CredentialService
from app.services.deployment.service import DeploymentService
from app.services.journey import JourneyService
from app.services.mcp_access import MCPAccessService
from app.services.projects import ProjectService
from app.services.settings import SettingsService
from app.services.sources import SourceService
from app.services.users import UserService


@dataclass(frozen=True, slots=True)
class ServiceContainer:
    auth: AuthService
    users: UserService
    projects: ProjectService
    sources: SourceService
    credentials: CredentialService
    audit: AuditService
    deployments: DeploymentService
    journey: JourneyService
    mcp_access: MCPAccessService
    settings: SettingsService
    ai: AIProvider
    build_admission: BuildAdmissionDispatcher
    builds: BuildService
    cleanup: CleanupService
