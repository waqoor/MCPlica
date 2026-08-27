from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.database import DatabaseClient
from app.core.config import Settings
from app.core.exceptions import DeployabilityError, MCPlicaError, NotFoundError
from app.domain.auth import UserRole
from app.domain.builds import TERMINAL_STATUSES, BuildRecord, BuildStatus
from app.domain.deployments import DeploymentStatus
from app.domain.journey import (
    JourneySourceRecord,
    JourneyStepRecord,
    JourneyStepState,
    ProjectJourneyRecord,
)
from app.domain.sources import SourceKind
from app.domain.validation import ValidationStatus
from app.repositories.builds import BuildRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sources import SourceRepository
from app.repositories.validation import ValidationRepository
from app.services.builds.readiness import credential_mapping_readiness
from app.services.deployment.preflight import DeploymentPreflight
from app.services.mcp_access import MCPAccessService
from app.services.settings import OperationalSettingsProvider
from app.services.sources import SourceService


class JourneyService:
    """Build a resumable setup view from authoritative durable records."""

    def __init__(
        self,
        database: DatabaseClient,
        projects: ProjectRepository,
        sources: SourceRepository,
        builds: BuildRepository,
        validation: ValidationRepository,
        credentials: CredentialRepository,
        deployments: DeploymentRepository,
        source_service: SourceService,
        access_service: MCPAccessService,
        preflight: DeploymentPreflight,
        operational: OperationalSettingsProvider,
        defaults: Settings,
    ) -> None:
        self._database = database
        self._projects = projects
        self._sources = sources
        self._builds = builds
        self._validation = validation
        self._credentials = credentials
        self._deployments = deployments
        self._source_service = source_service
        self._access_service = access_service
        self._preflight = preflight
        self._operational = operational
        self._defaults = defaults

    async def get(
        self,
        project_id: UUID,
        *,
        requested_build_id: UUID | None,
        actor_role: UserRole,
    ) -> ProjectJourneyRecord:
        async with self._database.session_scope() as session:
            project = await self._projects.get(session, project_id)
            if project is None:
                raise NotFoundError("Project was not found")
            bindings = await self._sources.latest_bound_versions(session, project_id)
            builds = await self._builds.list_for_project(session, project_id, limit=500)
            selected = await self._select_build(
                session,
                project_id=project_id,
                active_build_id=project.active_build_id,
                requested_build_id=requested_build_id,
                builds=builds,
            )
            report = (
                await self._validation.get_report(session, selected.id)
                if selected is not None
                else None
            )
            current_credentials = await self._credentials.list(session, project_id)
            active_deployment = (
                await self._deployments.get(session, project.active_deployment_id)
                if project.active_deployment_id is not None
                else None
            )
            deployment_in_progress = await self._deployments.has_in_progress(session, project_id)

        primary = next(
            (
                binding
                for binding in bindings
                if binding.source.is_primary
                and binding.source.kind in {SourceKind.OPENAPI, SourceKind.API_INVENTORY}
            ),
            None,
        )
        discovery = None
        discovery_error: MCPlicaError | None = None
        if primary is not None:
            try:
                discovery = await self._source_service.discover_configuration(project_id)
            except MCPlicaError as exc:
                discovery_error = exc

        access = await self._access_service.get_status(project_id)
        settings = await self._operational.get_operational()
        admin = actor_role is UserRole.ADMIN
        can_deploy = admin or (actor_role is UserRole.BUILDER and settings.builders_can_deploy)

        mapping = (
            credential_mapping_readiness(discovery, current_credentials)
            if discovery is not None
            else None
        )
        current_source_ids = [binding.version.id for binding in bindings]
        build_stale = selected is not None and (
            selected.executable_configuration_sha256 is None
            or discovery is None
            or selected.executable_configuration_sha256 != discovery.configuration_sha256
        )
        validation_complete = bool(
            report is not None
            and report.overall_status is ValidationStatus.PASS
            and report.coverage_percent == 100
            and report.blocking_error_count == 0
            and report.operation_generated_count == report.operation_expected_count
        )
        active_matches = bool(
            selected is not None
            and active_deployment is not None
            and active_deployment.build_id == selected.id
            and active_deployment.status is DeploymentStatus.RUNNING
        )

        preflight_ready = False
        deployability_code: str | None = None
        deployability_remediation: str | None = None
        if not project.is_enabled:
            deployability_code = "PROJECT_DISABLED"
            deployability_remediation = "Enable the project before deployment."
        elif selected is None or selected.status is not BuildStatus.READY:
            deployability_code = "BUILD_NOT_READY"
            deployability_remediation = "Create or select a READY build."
        elif build_stale:
            deployability_code = "BUILD_INPUTS_STALE"
            deployability_remediation = (
                "Create a new build from the current source and routing configuration."
            )
        elif not validation_complete:
            deployability_code = "VALIDATION_NOT_PASSED"
            deployability_remediation = "Resolve blocking validation findings and rebuild."
        else:
            async with self._database.session_scope() as session:
                deployable_build = await self._deployments.get_build(session, selected.id)
                if deployable_build is None or deployable_build.project_id != project_id:
                    raise NotFoundError("Build was not found for this project")
                try:
                    await self._preflight.validate(
                        session,
                        project_id=project_id,
                        hostname=project.mcp_hostname,
                        build=deployable_build,
                        runtime_version=self._defaults.mcp_runtime_version,
                    )
                    preflight_ready = True
                except DeployabilityError as exc:
                    deployability_code = _detail_text(exc.details, "reason_code", exc.code)
                    deployability_remediation = _detail_text(
                        exc.details,
                        "remediation",
                        "Resolve deployment preflight findings before retrying.",
                    )
        if preflight_ready and deployment_in_progress and not active_matches:
            preflight_ready = False
            deployability_code = "DEPLOYMENT_IN_PROGRESS"
            deployability_remediation = (
                "Wait for the current deployment transition to reach a terminal state."
            )

        executable_complete = primary is not None
        routing_complete = bool(discovery is not None and discovery.routing_complete)
        credential_complete = bool(routing_complete and mapping is not None and mapping.complete)
        build_started = bool(
            selected is not None
            and selected.status not in {BuildStatus.FAILED, BuildStatus.CANCELLED}
            and not build_stale
        )
        build_ready = bool(
            selected is not None and selected.status is BuildStatus.READY and not build_stale
        )
        completed = {
            1: True,
            2: executable_complete,
            # Documentation is explicitly optional, but existing records are hydrated.
            3: executable_complete,
            4: routing_complete,
            5: credential_complete,
            6: build_started,
            7: build_ready,
            8: validation_complete and build_ready,
            9: access.configured,
            10: active_matches,
        }
        resume_step = next(
            (number for number in range(2, 11) if not completed[number]),
            10,
        )
        stale_steps: set[int] = set()
        if selected is not None and (
            build_stale or selected.status in {BuildStatus.FAILED, BuildStatus.CANCELLED}
        ):
            stale_steps.update({7, 8, 10})
        if report is not None and not validation_complete:
            stale_steps.add(8)
        if active_deployment is not None and not active_matches:
            stale_steps.add(10)

        deployable = preflight_ready and can_deploy and not active_matches
        if preflight_ready and not can_deploy:
            deployability_code = "DEPLOYMENT_PERMISSION_REQUIRED"
            deployability_remediation = (
                "Ask an administrator to deploy or enable Builder deployment permission."
            )

        step_messages = self._step_messages(
            selected=selected,
            discovery_error=discovery_error,
            mapping_unresolved=(
                list(mapping.unresolved_operation_keys) if mapping is not None else []
            ),
            access_remediation=access.remediation,
            deployability_code=deployability_code,
            deployability_remediation=deployability_remediation,
        )
        steps = [
            self._step(
                number,
                complete=completed[number],
                current=number == resume_step,
                stale=number in stale_steps,
                authorized=self._authorized(
                    number,
                    admin=admin,
                    can_deploy=can_deploy,
                    credential_complete=credential_complete,
                    access_complete=access.configured,
                ),
                message=step_messages.get(number),
            )
            for number in range(1, 11)
        ]
        return ProjectJourneyRecord(
            project_id=project_id,
            requested_build_id=requested_build_id,
            selected_build_id=selected.id if selected is not None else None,
            active_build_id=project.active_build_id,
            active_deployment_id=project.active_deployment_id,
            resume_step=resume_step,
            steps=steps,
            sources=[
                JourneySourceRecord(
                    id=binding.source.id,
                    version_id=binding.version.id,
                    kind=binding.source.kind,
                    name=binding.source.name,
                    is_primary=binding.source.is_primary,
                )
                for binding in bindings
            ],
            source_version_ids=current_source_ids,
            routing_complete=routing_complete,
            credential_mapping_required=bool(mapping and mapping.required),
            credential_mapping_complete=credential_complete,
            bound_security_schemes=(
                list(mapping.bound_scheme_names) if mapping is not None else []
            ),
            access_mode=access.mode,
            access_configured=access.configured,
            access_runtime_effect_state=access.runtime_effect_state,
            access_remediation=access.remediation,
            build_status=selected.status if selected is not None else None,
            build_stale=build_stale,
            validation_status=report.overall_status if report is not None else None,
            validation_complete=validation_complete,
            active_deployment_status=(
                active_deployment.status if active_deployment is not None else None
            ),
            deployment_transition_in_progress=deployment_in_progress,
            preflight_ready=preflight_ready,
            deployable=deployable,
            deployability_reason_code=deployability_code,
            deployability_remediation=deployability_remediation,
            can_manage_credentials=admin,
            can_manage_mcp_access=admin,
            can_deploy=can_deploy,
        )

    async def _select_build(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        active_build_id: UUID | None,
        requested_build_id: UUID | None,
        builds: list[BuildRecord],
    ) -> BuildRecord | None:
        if requested_build_id is not None:
            requested = await self._builds.get(session, requested_build_id)
            if requested is None or requested.project_id != project_id:
                raise NotFoundError("Build was not found for this project")
            return requested
        if active_build_id is not None:
            active = next((build for build in builds if build.id == active_build_id), None)
            if active is None:
                # History pages are bounded. The authoritative active pointer
                # may legitimately reference an older immutable build outside
                # that window, so resolve it directly instead of silently
                # presenting a newer build as selected.
                active = await self._builds.get(session, active_build_id)
                if active is None or active.project_id != project_id:
                    raise NotFoundError("The Project active Build reference is invalid")
            return active
        pipeline = next(
            (build for build in builds if build.status not in TERMINAL_STATUSES),
            None,
        )
        return pipeline or (builds[0] if builds else None)

    @staticmethod
    def _authorized(
        number: int,
        *,
        admin: bool,
        can_deploy: bool,
        credential_complete: bool,
        access_complete: bool,
    ) -> bool:
        if number == 5 and not credential_complete:
            return admin
        if number == 9 and not access_complete:
            return admin
        if number == 10:
            return can_deploy
        return True

    @staticmethod
    def _step(
        number: int,
        *,
        complete: bool,
        current: bool,
        stale: bool,
        authorized: bool,
        message: tuple[str, str, str | None] | None,
    ) -> JourneyStepRecord:
        state = (
            JourneyStepState.COMPLETE
            if complete
            else JourneyStepState.CURRENT
            if current
            else JourneyStepState.STALE
            if stale
            else JourneyStepState.LOCKED
        )
        relevant = None if complete else message
        return JourneyStepRecord(
            number=number,
            state=state,
            authorized=authorized,
            reason_code=relevant[0] if relevant is not None else None,
            message=relevant[1] if relevant is not None else None,
            remediation=relevant[2] if relevant is not None else None,
        )

    @staticmethod
    def _step_messages(
        *,
        selected: BuildRecord | None,
        discovery_error: MCPlicaError | None,
        mapping_unresolved: list[str],
        access_remediation: str | None,
        deployability_code: str | None,
        deployability_remediation: str | None,
    ) -> dict[int, tuple[str, str, str | None]]:
        result: dict[int, tuple[str, str, str | None]] = {
            2: (
                "EXECUTABLE_SOURCE_REQUIRED",
                "A versioned primary executable source is required.",
                "Attach a valid OpenAPI or API Inventory source.",
            ),
            4: (
                discovery_error.code if discovery_error is not None else "ROUTING_INCOMPLETE",
                str(discovery_error)
                if discovery_error is not None
                else "Every operation must resolve to one applicable upstream server.",
                "Resolve invalid or ambiguous server selections.",
            ),
            5: (
                "CREDENTIAL_MAPPING_INCOMPLETE",
                (
                    "Upstream credential mapping is incomplete for operations: "
                    + ", ".join(mapping_unresolved[:10])
                    if mapping_unresolved
                    else "Upstream credential mapping is incomplete."
                ),
                "Ask an administrator to bind one compatible active credential per operation.",
            ),
            9: (
                "MCP_ACCESS_INCOMPLETE",
                "Inbound MCP access is not deployable.",
                access_remediation,
            ),
            10: (
                deployability_code or "DEPLOYMENT_REQUIRED",
                "The selected build is not the active healthy runtime.",
                deployability_remediation,
            ),
        }
        if selected is None:
            result[6] = (
                "BUILD_REQUIRED",
                "No build exists for the current source configuration.",
                "Start an immutable build.",
            )
            result[7] = result[6]
        elif selected.status in {BuildStatus.FAILED, BuildStatus.CANCELLED}:
            result[6] = (
                f"BUILD_{selected.status.value}",
                selected.error_summary or f"Build #{selected.sequence} did not complete.",
                "Return to build creation after correcting the reported cause.",
            )
            result[7] = result[6]
        else:
            result[7] = (
                f"BUILD_{selected.status.value}",
                f"Build #{selected.sequence} has not reached READY.",
                "Wait for a terminal status; failed and cancelled builds cannot continue.",
            )
        result[8] = (
            "VALIDATION_NOT_PASSED",
            "The selected build has no complete passing validation report.",
            "Resolve blocking findings and create a new build.",
        )
        return result


def _detail_text(
    details: Mapping[str, Any],
    key: str,
    default: str,
) -> str:
    value = details.get(key)
    return value if isinstance(value, str) and value else default
