from dataclasses import dataclass

from app.providers.ai.base import AIProvider
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.builds import BuildService
from app.services.credentials import CredentialService
from app.services.deployment.service import DeploymentService
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
    mcp_access: MCPAccessService
    settings: SettingsService
    ai: AIProvider
    builds: BuildService
