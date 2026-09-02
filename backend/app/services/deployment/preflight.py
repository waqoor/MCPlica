import hashlib
import hmac
from dataclasses import dataclass
from typing import Never
from uuid import UUID

from mcp_contracts import MCPManifest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import DeployabilityError, MCPlicaError, PayloadTooLargeError
from app.domain.credentials import CredentialScheme
from app.domain.deployments import DeployableBuildRecord, MCPAuthConfigRecord
from app.providers.storage import ArtifactStorage
from app.repositories.credentials import CredentialRepository, EncryptedCredential
from app.repositories.mcp_access import MCPAccessRepository, MCPTokenVerifierRecord
from app.services.builds.configuration_identity import (
    ExecutableConfigurationProvider,
)
from app.services.deployment.secret_materializer import materialize_inbound_auth
from app.validators.manifest import validate_manifest


@dataclass(frozen=True, slots=True)
class DeploymentPreflightResult:
    manifest: MCPManifest
    manifest_bytes: bytes
    auth_config: MCPAuthConfigRecord
    token_verifiers: list[MCPTokenVerifierRecord]


class DeploymentPreflight:
    """Side-effect-free deployment invariants shared by the API and worker."""

    def __init__(
        self,
        access: MCPAccessRepository,
        credentials: CredentialRepository,
        configuration: ExecutableConfigurationProvider,
        artifacts: ArtifactStorage,
        settings: Settings,
        *,
        manifest_max_bytes: int,
    ) -> None:
        self._access = access
        self._credentials = credentials
        self._configuration = configuration
        self._artifacts = artifacts
        self._settings = settings
        self._manifest_max_bytes = manifest_max_bytes

    async def validate(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        hostname: str,
        build: DeployableBuildRecord,
        runtime_version: str,
        require_current_configuration: bool = True,
    ) -> DeploymentPreflightResult:
        if not build.source_binding_metadata_trustworthy:
            self._reject(
                "BUILD_SOURCE_BINDING_IDENTITY_MISSING",
                "Build predates immutable source binding metadata",
                field="build_id",
                remediation="Create a new build from the currently selected source versions.",
            )
        if build.executable_configuration_sha256 is None:
            self._reject(
                "BUILD_CONFIGURATION_IDENTITY_MISSING",
                "Build predates executable configuration identity tracking",
                field="build_id",
                remediation="Create a new build from the current source and routing configuration.",
            )
        if require_current_configuration:
            current_configuration_sha256 = await self._configuration.current_sha256(
                session,
                project_id,
            )
            if not hmac.compare_digest(
                build.executable_configuration_sha256,
                current_configuration_sha256,
            ):
                self._reject(
                    "BUILD_INPUTS_STALE",
                    "Build source or routing configuration is no longer current",
                    field="build_id",
                    remediation=(
                        "Create a new build from the current source and routing configuration."
                    ),
                )
        if not build.manifest_storage_key or not build.manifest_sha256:
            self._reject(
                "MANIFEST_MISSING",
                "Build has no immutable manifest artifact",
                field="build_id",
                remediation="Create a new successful build before deployment.",
            )
        effective_manifest_limit = min(
            build.runtime_manifest_max_bytes,
            self._manifest_max_bytes,
        )
        try:
            manifest_bytes = await self._artifacts.get(
                build.manifest_storage_key,
                max_bytes=effective_manifest_limit,
            )
        except PayloadTooLargeError as exc:
            self._reject(
                "MANIFEST_EXCEEDS_RUNTIME_LIMIT",
                "Build manifest exceeds the effective generic-runtime byte limit",
                field="build_id",
                remediation="Create a new build with less embedded manifest content.",
                cause=exc,
            )
        except Exception as exc:
            self._reject(
                "MANIFEST_UNAVAILABLE",
                "Build manifest artifact is unavailable",
                field="build_id",
                remediation="Rebuild the project to restore the immutable artifact.",
                cause=exc,
            )
        if len(manifest_bytes) > effective_manifest_limit:
            self._reject(
                "MANIFEST_EXCEEDS_RUNTIME_LIMIT",
                "Build manifest exceeds the effective generic-runtime byte limit",
                field="build_id",
                remediation="Create a new build with less embedded manifest content.",
            )
        assert build.manifest_sha256 is not None
        if hashlib.sha256(manifest_bytes).hexdigest() != build.manifest_sha256.lower():
            self._reject(
                "MANIFEST_HASH_MISMATCH",
                "Build manifest artifact failed identity verification",
                field="build_id",
                remediation="Rebuild the project; do not deploy the damaged artifact.",
            )
        try:
            manifest = MCPManifest.model_validate_json(manifest_bytes)
            validate_manifest(manifest, runtime_version=runtime_version)
        except (PydanticValidationError, MCPlicaError, ValueError) as exc:
            self._reject(
                "MANIFEST_INVALID",
                "Build manifest is incompatible with the configured runtime",
                field="build_id",
                remediation="Create a new build with the current compiler and runtime contract.",
                cause=exc,
            )
        if manifest.project.id != str(project_id) or manifest.build.build_id != str(build.id):
            self._reject(
                "MANIFEST_IDENTITY_MISMATCH",
                "Build manifest identity does not match the deployment target",
                field="build_id",
                remediation="Select the READY build belonging to this project.",
            )

        auth_config = await self._access.get_config(session, project_id)
        if auth_config is None:
            self._reject(
                "ACCESS_CONFIG_MISSING",
                "Inbound MCP authentication is not configured",
                field="access.mode",
                remediation="Configure static bearer or OIDC access before deployment.",
            )
        verifiers = await self._access.active_verifiers(session, project_id)
        try:
            materialize_inbound_auth(
                hostname=hostname,
                config=auth_config,
                verifiers=verifiers,
                settings=self._settings,
            )
        except (PydanticValidationError, MCPlicaError, ValueError) as exc:
            self._reject(
                "ACCESS_CONFIG_INVALID",
                "Inbound MCP authentication is incomplete or incompatible",
                field="access",
                remediation=(
                    "Add an unexpired static token or complete the OIDC configuration "
                    "for this environment."
                ),
                cause=exc,
            )

        required_profile_ids = {
            tool.security_profile_ref
            for tool in manifest.enabled_tools()
            if tool.security_profile_ref is not None
        }
        profiles = {profile.id: profile for profile in manifest.auth_profiles}
        missing_profiles = required_profile_ids - set(profiles)
        if missing_profiles:
            self._reject(
                "AUTH_PROFILE_MISSING",
                "Manifest references an unknown upstream authentication profile",
                field="build_id",
                remediation="Rebuild after correcting source authentication mappings.",
            )
        references: set[UUID] = set()
        for profile_id in required_profile_ids:
            reference = profiles[profile_id].credential_ref
            try:
                references.add(UUID(reference or ""))
            except ValueError as exc:
                self._reject(
                    "CREDENTIAL_REFERENCE_INVALID",
                    "Manifest contains an invalid upstream credential reference",
                    field="credentials",
                    remediation="Rebuild after binding an active project credential.",
                    cause=exc,
                )
        credentials = await self._credentials.get_encrypted_many(
            session,
            project_id=project_id,
            credential_ids=references,
        )
        by_id = {credential.metadata.id: credential for credential in credentials}
        if set(by_id) != references:
            self._reject(
                "CREDENTIAL_MISSING",
                "A required upstream credential is unavailable",
                field="credentials",
                remediation="Bind every required source security scheme to an active credential.",
            )
        for profile_id in required_profile_ids:
            profile = profiles[profile_id]
            credential = by_id[UUID(profile.credential_ref or "")]
            self._validate_credential(profile.type, profile.location, credential)
        return DeploymentPreflightResult(
            manifest=manifest,
            manifest_bytes=manifest_bytes,
            auth_config=auth_config,
            token_verifiers=verifiers,
        )

    def _validate_credential(
        self,
        profile_type: str,
        profile_location: str | None,
        credential: EncryptedCredential,
    ) -> None:
        if credential.metadata.revoked_at is not None:
            self._reject(
                "CREDENTIAL_REVOKED",
                "A required upstream credential is revoked",
                field="credentials",
                remediation="Bind an active replacement credential and create a new build.",
            )
        expected: dict[str, set[CredentialScheme]] = {
            "bearer": {CredentialScheme.BEARER},
            "basic": {CredentialScheme.BASIC},
            "oauth2_client_credentials": {CredentialScheme.OAUTH2_CLIENT_CREDENTIALS},
            "static_header": {CredentialScheme.STATIC_HEADERS},
            "api_key": {
                CredentialScheme.API_KEY_HEADER
                if profile_location == "header"
                else CredentialScheme.API_KEY_QUERY
            },
        }
        if credential.metadata.scheme_type not in expected.get(profile_type, set()):
            self._reject(
                "CREDENTIAL_SCHEME_MISMATCH",
                "A required upstream credential no longer matches its manifest profile",
                field="credentials",
                remediation="Correct the source-scheme binding and create a new build.",
            )

    @staticmethod
    def _reject(
        reason_code: str,
        message: str,
        *,
        field: str,
        remediation: str,
        cause: Exception | None = None,
    ) -> Never:
        error = DeployabilityError(
            message,
            details={
                "reason_code": reason_code,
                "field": field,
                "remediation": remediation,
            },
        )
        if cause is not None:
            raise error from cause
        raise error
